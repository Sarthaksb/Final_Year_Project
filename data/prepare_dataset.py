"""
data/prepare_dataset.py
=======================
Prepares the ISIC 2019 dataset for training.

Expected Google Drive layout (set DRIVE_ROOT in your .env or pass --drive_root):
    /content/drive/MyDrive/dermatology/
    ├── ISIC_2019_Training_Input/             ← all .jpg images (25,331 files)
    │   ├── ISIC_0000000.jpg
    │   └── ...
    ├── ISIC_2019_Training_GroundTruth.csv    ← official label CSV  (REQUIRED)
    └── ISIC_2019_Training_Metadata.csv       ← lesion/lesion IDs  (REQUIRED)

Download both files from: https://challenge.isic-archive.com/data/#2019

What this script does:
  0. Loads label CSV, filters UNK rows, validates one-hot labels
  1. Validates every image file exists; removes corrupt/missing images
  2. Removes exact duplicate image IDs (keeps first occurrence)
  3. Reports raw class distribution
  4. Loads ISIC_2019_Training_Metadata.csv and assigns a group_id per image:
       - Images with a valid lesion_id  → group_id = lesion_id
       - Images with lesion_id = NaN   → group_id = "SYNTH_<image_id>"
         (each NaN image is its own singleton group — no cross-leakage)
  5. Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) stratified split: train / val / test (70 / 15 / 15)
       Uses StratifiedGroupKFold so:
         a) All images of the same lesion stay in one split
         b) Class distribution is kept reasonably balanced
         c) Zero-overlap assertions are enforced
  6. Prints class distribution and image/group counts for every split
  7. Computes inverse-frequency class weights from the train split
  8. Saves three CSVs: train.csv, val.csv, test.csv → data/processed/
       Columns: image, label, class_name, group_id
  9. Saves dataset_summary.txt → data/

Run on Colab after mounting Drive:
    python data/prepare_dataset.py --drive_root /content/drive/MyDrive/dermatology
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, UnidentifiedImageError
from sklearn.model_selection import StratifiedGroupKFold
from tqdm import tqdm

# ── ISIC 2019 class definitions ───────────────────────────────────────────────
# Column names in the ground-truth CSV (one-hot encoded)
ISIC2019_CLASSES = ["MEL", "NV", "BCC", "AK", "BKL", "DF", "VASC", "SCC"]

CLASS_DESCRIPTIONS = {
    "MEL":  "Melanoma",
    "NV":   "Melanocytic Nevus",
    "BCC":  "Basal Cell Carcinoma",
    "AK":   "Actinic Keratosis",
    "BKL":  "Benign Keratosis-like Lesion",
    "DF":   "Dermatofibroma",
    "VASC": "Vascular Lesion",
    "SCC":  "Squamous Cell Carcinoma",
}


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare ISIC 2019 dataset")
    p.add_argument(
        "--dataset_root",
        type=str,
        default=os.environ.get("DATASET_ROOT", "/content/isic"),
        help="Root folder containing the ISIC 2019 files",
    )
    p.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Where to save processed CSVs. Defaults to <project_root>/data/processed/",
    )
    p.add_argument(
        "--val_ratio",
        type=float,
        default=0.15,
        help="Fraction of total data for validation (default 0.15)",
    )
    p.add_argument(
        "--test_ratio",
        type=float,
        default=0.15,
        help="Fraction of total data for test (default 0.15)",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    return p.parse_args()


# ── Path resolution ───────────────────────────────────────────────────────────

def resolve_paths(dataset_root: str) -> tuple[Path, Path, Path, Path]:
    """
    Return (image_dir, ground_truth_csv, metadata_csv, root_path).
    Hard-stops if required files are missing.
    """
    root        = Path(dataset_root)
    img_dir     = root / "ISIC_2019_Training_Input"
    gt_csv      = root / "ISIC_2019_Training_GroundTruth.csv"
    meta_csv    = root / "ISIC_2019_Training_Metadata.csv"

    if not root.exists():
        sys.exit(
            f"\n[ERROR] Dataset root not found: {root}\n"
            "  → Make sure the dataset is extracted and --dataset_root is correct."
        )
    if not img_dir.exists():
        sys.exit(
            f"\n[ERROR] Image folder not found: {img_dir}\n"
            "  → Expected folder name: ISIC_2019_Training_Input\n"
            "  → Download from: https://challenge.isic-archive.com/data/#2019"
        )
    if not gt_csv.exists():
        sys.exit(
            f"\n[ERROR] Ground-truth CSV not found: {gt_csv}\n"
            "  → Expected file name: ISIC_2019_Training_GroundTruth.csv\n"
            "  → Download from: https://challenge.isic-archive.com/data/#2019"
        )
    if not meta_csv.exists():
        sys.exit(
            f"\n[ERROR] Metadata CSV not found: {meta_csv}\n"
            "  → Expected file name: ISIC_2019_Training_Metadata.csv\n"
            "  → Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) splitting requires this file.\n"
            "  → Download from: https://challenge.isic-archive.com/data/#2019\n"
            "  → The metadata CSV is a SEPARATE download from the ground-truth CSV."
        )

    return img_dir, gt_csv, meta_csv, root


# ── Label loading (with UNK filter) ──────────────────────────────────────────

def load_labels(csv_path: Path) -> pd.DataFrame:
    """
    Load ground-truth CSV and convert one-hot encoding to integer label column.

    UNK filter: The official ISIC_2019_Training_GroundTruth.csv has a 9th
    column 'UNK' for images that don't belong to any of the 8 classes.
    Rows where UNK=1 are DROPPED before argmax — otherwise a row of all-zeros
    across the 8 class columns would silently map to label=0 (MEL).
    """
    df = pd.read_csv(csv_path)

    # Validate expected class columns exist
    missing = [c for c in ISIC2019_CLASSES if c not in df.columns]
    if missing:
        sys.exit(f"\n[ERROR] Ground-truth CSV missing expected class columns: {missing}")

    total_before = len(df)

    # ── Step 1: Drop rows where UNK == 1 ────────────────────────────────────
    if "UNK" in df.columns:
        unk_mask  = df["UNK"] == 1.0
        unk_count = unk_mask.sum()
        if unk_count > 0:
            print(f"   [UNK filter] Dropping {unk_count:,} rows with UNK=1 "
                  f"(not one of the 8 diagnostic classes)")
            df = df[~unk_mask].copy()
        else:
            print("   [UNK filter] No UNK rows found.")
    else:
        print("   [UNK filter] No 'UNK' column in CSV — skipping UNK filter.")

    # ── Step 2: Validate each row has exactly one '1' in the 8 class columns ─
    row_sums     = df[ISIC2019_CLASSES].sum(axis=1)
    invalid_mask = row_sums != 1.0
    invalid_count = invalid_mask.sum()
    if invalid_count > 0:
        print(f"   [Label validation] Dropping {invalid_count:,} rows with "
              f"ambiguous one-hot labels (sum != 1 across 8 class columns)")
        df = df[~invalid_mask].copy()

    removed_total = total_before - len(df)
    print(f"   [Label cleaning] {removed_total:,} rows removed total "
          f"(UNK + invalid). {len(df):,} valid rows remain.")

    # ── Step 3: Safe argmax — all rows now have exactly one '1' ─────────────
    df["label"]      = df[ISIC2019_CLASSES].values.argmax(axis=1)
    df["class_name"] = df["label"].map(lambda i: ISIC2019_CLASSES[i])
    return df[["image", "label", "class_name"]]


# ── Image validation ──────────────────────────────────────────────────────────

def check_images(df: pd.DataFrame, img_dir: Path) -> pd.DataFrame:
    """
    For each row:
      1. Check the image file exists.
      2. Try opening with Pillow to catch corrupt files.

    Portable paths: Returns a cleaned DataFrame with columns
    [image, label, class_name] only. The absolute filepath is NOT stored
    in the CSV — it is reconstructed at training time from img_dir.
    """
    print("\n[1/5] Validating images ...")
    records       = []
    missing_count = 0
    corrupt_count = 0

    for _, row in tqdm(df.iterrows(), total=len(df), unit="img"):
        img_id   = row["image"]
        filepath = img_dir / f"{img_id}.jpg"

        if not filepath.exists():
            missing_count += 1
            continue

        try:
            with Image.open(filepath) as img:
                img.verify()
        except (UnidentifiedImageError, Exception) as e:
            corrupt_count += 1
            print(f"   [CORRUPT] {img_id}: {e}")
            continue

        # Store only image ID, label, class_name — NOT the absolute filepath
        records.append({
            "image":      img_id,
            "label":      int(row["label"]),
            "class_name": row["class_name"],
        })

    print(f"   ✓ Valid images     : {len(records):,}")
    print(f"   ✗ Missing files    : {missing_count:,}")
    print(f"   ✗ Corrupt images   : {corrupt_count:,}")
    return pd.DataFrame(records)


# ── Duplicate removal ─────────────────────────────────────────────────────────

def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows with duplicate image IDs (keep first occurrence)."""
    before = len(df)
    df     = df.drop_duplicates(subset=["image"], keep="first").reset_index(drop=True)
    after  = len(df)
    print(f"\n[2/5] Duplicate removal: {before-after:,} duplicates dropped → {after:,} images remain")
    return df


# ── Class distribution printer ────────────────────────────────────────────────

def class_distribution(df: pd.DataFrame, label: str = "") -> dict:
    """Print and return class distribution as {class_name: count}."""
    total = len(df)
    dist  = df["class_name"].value_counts().to_dict()
    unique_groups = df["group_id"].nunique() if "group_id" in df.columns else "N/A"

    print(f"\n{'─'*60}")
    print(f"  Class distribution {label}")
    if "group_id" in df.columns:
        print(f"  Images: {total:,}  |  Unique groups (lesions): {unique_groups:,}")
    print(f"{'─'*60}")
    print(f"  {'Class':<6}  {'Description':<35}  {'Count':>6}  {'%':>6}")
    print(f"{'─'*60}")
    for cls in ISIC2019_CLASSES:
        count = dist.get(cls, 0)
        pct   = 100.0 * count / total if total > 0 else 0
        print(f"  {cls:<6}  {CLASS_DESCRIPTIONS[cls]:<35}  {count:>6,}  {pct:>5.1f}%")
    print(f"{'─'*60}")
    print(f"  {'TOTAL':<6}  {'':35}  {total:>6,}  100.0%")
    print(f"{'─'*60}")
    return dist


# ── Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) group ID assignment ─────────────────────────────────────────

def assign_group_ids(df: pd.DataFrame, meta_csv: Path) -> pd.DataFrame:
    """
    Load ISIC_2019_Training_Metadata.csv and merge lesion_id onto the image
    dataframe, then assign a group_id for splitting:

      - Images with a valid lesion_id  → group_id = lesion_id
      - Images with lesion_id = NaN   → group_id = "SYNTH_<image_id>"
        Each NaN image gets its own unique singleton group so MSK anonymous
        images cannot cause cross-split contamination.

    Returns df with a 'group_id' column added.
    """
    print(f"\n[3a/5] Loading lesion metadata: {meta_csv} ...")
    meta = pd.read_csv(meta_csv)

    if "lesion_id" not in meta.columns:
        sys.exit(
            "\n[ERROR] ISIC_2019_Training_Metadata.csv does not contain a 'lesion_id' column.\n"
            "  → Verify you downloaded the correct metadata file from the ISIC Archive."
        )

    # Keep only the columns we need
    meta = meta[["image", "lesion_id"]].copy()

    total_meta  = len(meta)
    nan_count   = meta["lesion_id"].isna().sum()
    valid_count = total_meta - nan_count

    print(f"   Metadata rows      : {total_meta:,}")
    print(f"   Valid lesion_id   : {valid_count:,}")
    print(f"   Missing lesion_id : {nan_count:,}  "
          f"(MSK/anonymous images — each assigned a unique synthetic group)")

    # Merge metadata onto the cleaned image dataframe
    df = df.merge(meta, on="image", how="left")

    # Images in df that had no matching row in metadata at all
    unmatched = df["lesion_id"].isna().sum()
    if unmatched > valid_count:
        # Some images have no metadata entry at all (beyond the NaN lesion_ids)
        extra_unmatched = unmatched - nan_count
        if extra_unmatched > 0:
            print(f"   [WARNING] {extra_unmatched:,} images have no entry in the metadata CSV "
                  f"— treated as singleton groups.")

    # Assign group_id: real lesion_id or unique synthetic ID
    nan_mask = df["lesion_id"].isna()
    df["group_id"] = df["lesion_id"].astype(str)
    df.loc[nan_mask, "group_id"] = "SYNTH_" + df.loc[nan_mask, "image"]

    # Drop the raw lesion_id column (group_id is what we use from here on)
    df = df.drop(columns=["lesion_id"])

    real_groups   = df.loc[~nan_mask, "group_id"].nunique()
    synth_groups  = nan_mask.sum()
    total_groups  = df["group_id"].nunique()
    print(f"   Real lesion groups (HAM10000 + BCN): {real_groups:,}")
    print(f"   Synthetic singleton groups (MSK/NaN): {synth_groups:,}")
    print(f"   Total unique groups                 : {total_groups:,}")

    return df


# ── Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) stratified split ────────────────────────────────────────────

def split_dataset_lesion_level(
    df: pd.DataFrame,
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) stratified split using StratifiedGroupKFold.

    Guarantees:
      1. All images of the same lesion (group_id) stay in one split.
      2. Class distribution is kept reasonably balanced (best-effort).
      3. Zero-overlap assertions are verified after splitting.

    Split ratios target: train ≈ 70% | val ≈ 15% | test ≈ 15%
    Exact ratios will vary slightly because we must keep entire lesion groups
    together — we cannot split a lesion's images across boundaries.

    StratifiedGroupKFold approach:
      Round 1: n_splits = round(1 / test_ratio) → yields ~test_ratio test fold
      Round 2: n_splits = round(1 / adjusted_val_ratio) → yields ~val_ratio val fold
    """
    group_ids = df["group_id"]
    labels    = df["label"]
    n_total   = len(df)
    n_groups  = group_ids.nunique()

    print(f"\n[3/5] Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) stratified split ...")
    print(f"      Total images  : {n_total:,}")
    print(f"      Total groups  : {n_groups:,}")
    print(f"      Target ratios : train={1-val_ratio-test_ratio:.0%} / "
          f"val={val_ratio:.0%} / test={test_ratio:.0%}")

    # ── Round 1: Carve out test ───────────────────────────────────────────────
    # n_splits = 7 gives ~14.3% per fold → close to 15%
    n_splits_test = max(2, round(1.0 / test_ratio))
    sgkf_test = StratifiedGroupKFold(
        n_splits=n_splits_test, shuffle=True, random_state=seed
    )
    # Take the first fold's test indices
    train_val_idx, test_idx = next(
        sgkf_test.split(np.arange(n_total), labels, groups=group_ids)
    )

    train_val_df  = df.iloc[train_val_idx].copy().reset_index(drop=True)
    test_df       = df.iloc[test_idx].copy().reset_index(drop=True)

    # ── Round 2: Carve out val from train_val ─────────────────────────────────
    adjusted_val   = val_ratio / (1.0 - test_ratio)   # ~17.6% of train_val
    n_splits_val   = max(2, round(1.0 / adjusted_val))
    sgkf_val = StratifiedGroupKFold(
        n_splits=n_splits_val, shuffle=True, random_state=seed
    )
    train_sub_idx, val_sub_idx = next(
        sgkf_val.split(
            np.arange(len(train_val_df)),
            train_val_df["label"],
            groups=train_val_df["group_id"],
        )
    )

    train_df = train_val_df.iloc[train_sub_idx].copy().reset_index(drop=True)
    val_df   = train_val_df.iloc[val_sub_idx].copy().reset_index(drop=True)

    # ── Print size summary ────────────────────────────────────────────────────
    print(f"\n   Actual split sizes:")
    print(f"   Train : {len(train_df):,} images  ({100*len(train_df)/n_total:.1f}%)  "
          f"| {train_df['group_id'].nunique():,} unique groups")
    print(f"   Val   : {len(val_df):,} images  ({100*len(val_df)/n_total:.1f}%)  "
          f"| {val_df['group_id'].nunique():,} unique groups")
    print(f"   Test  : {len(test_df):,} images  ({100*len(test_df)/n_total:.1f}%)  "
          f"| {test_df['group_id'].nunique():,} unique groups")

    # ── Zero-overlap assertions ───────────────────────────────────────────────
    _verify_no_lesion_overlap(train_df, val_df, test_df)

    return train_df, val_df, test_df


def _verify_no_lesion_overlap(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> None:
    """
    Assert that no group_id (lesion) appears in more than one split.
    Raises AssertionError with a descriptive message if overlap is found.
    """
    train_groups = set(train_df["group_id"])
    val_groups   = set(val_df["group_id"])
    test_groups  = set(test_df["group_id"])

    tv_overlap = train_groups & val_groups
    tt_overlap = train_groups & test_groups
    vt_overlap = val_groups   & test_groups

    print("\n   Verifying zero lesion/group overlap across splits ...")

    if tv_overlap:
        raise AssertionError(
            f"[FAIL] Lesion overlap detected: train ∩ val = {len(tv_overlap):,} groups\n"
            f"       Example overlapping group_ids: {list(tv_overlap)[:5]}"
        )
    if tt_overlap:
        raise AssertionError(
            f"[FAIL] Lesion overlap detected: train ∩ test = {len(tt_overlap):,} groups\n"
            f"       Example overlapping group_ids: {list(tt_overlap)[:5]}"
        )
    if vt_overlap:
        raise AssertionError(
            f"[FAIL] Lesion overlap detected: val ∩ test = {len(vt_overlap):,} groups\n"
            f"       Example overlapping group_ids: {list(vt_overlap)[:5]}"
        )

    print("   ✅ train ∩ val  overlap : 0 groups")
    print("   ✅ train ∩ test overlap : 0 groups")
    print("   ✅ val   ∩ test overlap : 0 groups")
    print("   ✅ Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) integrity verified — no leakage.")


def verify_class_proportions(raw_dist, split_dist, split_name, total_raw, total_split):
    print(f"\n   Verifying {split_name} class proportions (target: ±2% of raw) ...")
    for cls in ISIC2019_CLASSES:
        raw_pct = 100.0 * raw_dist.get(cls, 0) / total_raw if total_raw > 0 else 0
        split_pct = 100.0 * split_dist.get(cls, 0) / total_split if total_split > 0 else 0
        diff = abs(split_pct - raw_pct)
        if diff > 2.0:
            print(f"      [WARN] {cls:6} deviated by {diff:.1f}% ({raw_pct:.1f}% -> {split_pct:.1f}%)")
        else:
            print(f"      [OK]   {cls:6} diff {diff:.1f}%")

# ── Class weights ─────────────────────────────────────────────────────────────

def compute_class_weights(train_df: pd.DataFrame) -> dict:
    """
    Inverse-frequency class weights for nn.CrossEntropyLoss(weight=...).
    Formula: weight[c] = total_samples / (num_classes * count[c])
    Higher weight = rarer class gets more gradient emphasis.
    """
    print("\n[4/5] Computing class weights (inverse-frequency) ...")
    counts    = train_df["class_name"].value_counts()
    total     = len(train_df)
    n_classes = len(ISIC2019_CLASSES)

    weights = {}
    print(f"\n  {'Class':<6}  {'Train Count':>12}  {'Weight':>8}")
    print(f"  {'─'*35}")
    for cls in ISIC2019_CLASSES:
        count       = counts.get(cls, 1)   # avoid div by zero
        w           = total / (n_classes * count)
        weights[cls] = round(w, 4)
        print(f"  {cls:<6}  {count:>12,}  {w:>8.4f}")

    print(
        "\n  Usage in train.py:\n"
        "    weights_tensor = torch.tensor([weights[c] for c in ISIC2019_CLASSES])\n"
        "    criterion = nn.CrossEntropyLoss(weight=weights_tensor.to(device))"
    )
    return weights


# ── Save outputs ──────────────────────────────────────────────────────────────

def save_outputs(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    raw_dist: dict,
    train_dist: dict,
    val_dist: dict,
    test_dist: dict,
    weights: dict,
    output_dir: Path,
    args: argparse.Namespace,
) -> None:
    """
    Save processed CSVs and dataset_summary.txt.

    CSV columns: image, label, class_name, group_id
    The group_id column allows post-hoc auditing of the split.
    """
    print(f"\n[5/5] Saving outputs to {output_dir} ...")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure column order is consistent
    cols = ["image", "label", "class_name", "group_id"]
    train_df[cols].to_csv(output_dir / "train.csv", index=False)
    val_df[cols].to_csv(output_dir / "val.csv",   index=False)
    test_df[cols].to_csv(output_dir / "test.csv",  index=False)
    print(f"   Saved: train.csv ({len(train_df):,} rows, "
          f"{train_df['group_id'].nunique():,} unique groups)")
    print(f"   Saved: val.csv   ({len(val_df):,} rows, "
          f"{val_df['group_id'].nunique():,} unique groups)")
    print(f"   Saved: test.csv  ({len(test_df):,} rows, "
          f"{test_df['group_id'].nunique():,} unique groups)")

    # ── Dataset summary report ────────────────────────────────────────────────
    summary_path = output_dir.parent / "dataset_summary.txt"
    total        = len(train_df) + len(val_df) + len(test_df)
    total_groups = (
        train_df["group_id"].nunique()
        + val_df["group_id"].nunique()
        + test_df["group_id"].nunique()
    )

    lines = [
        "=" * 65,
        "ISIC 2019 Dataset Summary — Lesion-Level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) Split",
        "=" * 65,
        f"Total images (after cleaning)  : {total:,}",
        f"Total unique groups (lesions) : {total_groups:,}",
        "",
        f"  Train : {len(train_df):,} images  ({100*len(train_df)/total:.1f}%)"
        f"  |  {train_df['group_id'].nunique():,} unique groups",
        f"  Val   : {len(val_df):,} images  ({100*len(val_df)/total:.1f}%)"
        f"  |  {val_df['group_id'].nunique():,} unique groups",
        f"  Test  : {len(test_df):,} images  ({100*len(test_df)/total:.1f}%)"
        f"  |  {test_df['group_id'].nunique():,} unique groups",
        "",
        "Split method: StratifiedGroupKFold (lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019), zero-overlap verified)",
        f"Random seed : {args.seed}",
        "",
        "-" * 65,
        "Raw class distribution (full dataset after cleaning):",
        "-" * 65,
    ]
    for cls in ISIC2019_CLASSES:
        count = raw_dist.get(cls, 0)
        pct   = 100.0 * count / total if total > 0 else 0
        lines.append(f"  {cls:<6}  {CLASS_DESCRIPTIONS[cls]:<35}  {count:>6,}  ({pct:.1f}%)")

    for split_name, dist, split_df in [
        ("Training", train_dist, train_df),
        ("Validation", val_dist, val_df),
        ("Test", test_dist, test_df),
    ]:
        split_total = len(split_df)
        lines += [
            "",
            "-" * 65,
            f"{split_name} split class distribution "
            f"({split_total:,} images, {split_df['group_id'].nunique():,} groups):",
            "-" * 65,
        ]
        for cls in ISIC2019_CLASSES:
            count = dist.get(cls, 0)
            pct   = 100.0 * count / split_total if split_total > 0 else 0
            lines.append(f"  {cls:<6}  {CLASS_DESCRIPTIONS[cls]:<35}  {count:>6,}  ({pct:.1f}%)")

    lines += [
        "",
        "-" * 65,
        "Class weights (inverse-frequency, from train split only):",
        "-" * 65,
    ]
    for cls in ISIC2019_CLASSES:
        lines.append(f"  {cls:<6}  weight = {weights[cls]:.4f}")

    lines += [
        "",
        "-" * 65,
        "Lesion overlap verification:",
        "-" * 65,
        "  train ∩ val  : 0 groups  ✅",
        "  train ∩ test : 0 groups  ✅",
        "  val   ∩ test : 0 groups  ✅",
        "",
        "CSV columns: image, label, class_name, group_id",
        "  group_id = lesion_id for identified lesions",
        "  group_id = SYNTH_<image_id> for anonymous (MSK) images",
        "",
        "Files produced:",
        "  data/processed/train.csv",
        "  data/processed/val.csv",
        "  data/processed/test.csv",
        "  data/dataset_summary.txt  (this file)",
        "=" * 65,
    ]

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"   Saved: {summary_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # Resolve project root
    project_root = Path(__file__).resolve().parent.parent
    output_dir   = Path(args.output_dir) if args.output_dir else project_root / "data" / "processed"

    print("=" * 65)
    print("ISIC 2019 Dataset Preparation — Lesion-Level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) Split")
    print("=" * 65)
    print(f"Dataset root : {args.dataset_root}")
    print(f"Output dir : {output_dir}")
    print(f"Seed       : {args.seed}")

    # ── Step 0: Resolve and validate all required paths ───────────────────────
    img_dir, gt_csv, meta_csv, _ = resolve_paths(args.dataset_root)

    # ── Step 1: Load and clean labels ─────────────────────────────────────────
    print(f"\n[0/5] Loading ground-truth CSV: {gt_csv} ...")
    df = load_labels(gt_csv)
    print(f"   Loaded {len(df):,} rows, {df['class_name'].nunique()} classes")

    # ── Step 2: Validate images ───────────────────────────────────────────────
    df = check_images(df, img_dir)

    # ── Step 3: Remove duplicates ─────────────────────────────────────────────
    df = remove_duplicates(df)

    # Print raw distribution (no group_id yet, so pass without it)
    df_for_dist = df.copy()
    df_for_dist["group_id"] = "N/A"   # placeholder so class_distribution works
    raw_dist = class_distribution(df_for_dist, label="(full dataset after cleaning)")

    # ── Step 4: Assign lesion group IDs ─────────────────────────────────────
    df = assign_group_ids(df, meta_csv)

    # ── Step 5: Lesion-level (grouped by lesion_id; lesion IDs are not provided in ISIC 2019) split ───────────────────────────────────────────
    train_df, val_df, test_df = split_dataset_lesion_level(
        df, args.val_ratio, args.test_ratio, args.seed
    )

    # Print per-split class distributions
    print()
    train_dist = class_distribution(train_df, label="(train split)")
    val_dist   = class_distribution(val_df,   label="(validation split)")
    test_dist  = class_distribution(test_df,  label="(test split)")

    # Verify proportions
    total_raw = len(df_for_dist)
    verify_class_proportions(raw_dist, train_dist, "Train", total_raw, len(train_df))
    verify_class_proportions(raw_dist, val_dist, "Val", total_raw, len(val_df))
    verify_class_proportions(raw_dist, test_dist, "Test", total_raw, len(test_df))


    # ── Step 6: Class weights ─────────────────────────────────────────────────
    weights = compute_class_weights(train_df)

    # ── Step 7: Save ──────────────────────────────────────────────────────────
    save_outputs(
        train_df, val_df, test_df,
        raw_dist, train_dist, val_dist, test_dist,
        weights, output_dir, args,
    )

    print("\n✅ Dataset preparation complete.")
    print(f"   CSV columns : image, label, class_name, group_id")
    print(f"   Next step   : run ml/classifier/train.py --dataset_root {args.dataset_root}")


if __name__ == "__main__":
    main()
