"""
ml/classifier/dataset.py
========================
PyTorch Dataset for ISIC 2019 skin lesion images.

Reads from the processed CSVs produced by data/prepare_dataset.py:
  data/processed/train.csv  |  val.csv  |  test.csv

Each CSV has columns: image, label (int 0-7), class_name, filepath

Usage:
    loaders = get_dataloaders(train_csv, val_csv, test_csv, batch_size=32)
    for images, labels in loaders["train"]:
        ...
"""

import os
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms

from ml.utils.logger import get_logger

log = get_logger(__name__)

# ── ImageNet normalization stats (used for all splits) ───────────────────────
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

ISIC2019_CLASSES = ["MEL", "NV", "BCC", "AK", "BKL", "DF", "VASC", "SCC"]


# ── Transforms ───────────────────────────────────────────────────────────────

def get_train_transform(img_size: int = 224) -> transforms.Compose:
    return transforms.Compose([
        transforms.RandomResizedCrop(img_size, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05),
        transforms.RandomRotation(degrees=20),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


def get_val_transform(img_size: int = 224) -> transforms.Compose:
    return transforms.Compose([
        transforms.Resize(int(img_size * 256 / 224)),   # 256 for 224 target
        transforms.CenterCrop(img_size),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])


# ── Dataset ───────────────────────────────────────────────────────────────────

class ISICDataset(Dataset):
    """
    ISIC 2019 skin lesion dataset.

    Args:
        csv_path  : Path to one of train.csv / val.csv / test.csv
                    Columns expected: image, label (int 0-7), class_name
        img_dir   : Directory containing the raw .jpg images.
                    Image path is reconstructed as: img_dir / f"{image_id}.jpg"
                    (FIX 2: paths are NOT stored in the CSV — reconstructed here)
        transform : torchvision transform to apply (train vs val/test)
    """

    def __init__(
        self,
        csv_path: str | Path,
        img_dir: str | Path,
        transform: Optional[Callable] = None,
    ):
        self.df = pd.read_csv(csv_path)
        self.img_dir = Path(img_dir)
        self.transform = transform

        # Validate required columns (filepath is no longer stored in the CSV)
        required = {"image", "label", "class_name"}
        missing = required - set(self.df.columns)
        if missing:
            raise ValueError(f"CSV {csv_path} is missing columns: {missing}")

        if not self.img_dir.exists():
            raise FileNotFoundError(
                f"Image directory not found: {self.img_dir}\n"
                f"  Pass the correct --drive_root so img_dir resolves correctly."
            )

        log.info(f"Loaded {len(self.df):,} samples from {csv_path} | img_dir={self.img_dir}")

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        row = self.df.iloc[idx]
        # Reconstruct path at runtime — not stored in CSV (Fix 2)
        img_path = self.img_dir / f"{row['image']}.jpg"
        img = Image.open(img_path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, int(row["label"])

    @property
    def labels(self) -> list[int]:
        """All integer labels — used to build WeightedRandomSampler."""
        return self.df["label"].tolist()

    @property
    def class_counts(self) -> dict[str, int]:
        return self.df["class_name"].value_counts().to_dict()


# ── WeightedRandomSampler builder ─────────────────────────────────────────────

def make_weighted_sampler(dataset: ISICDataset) -> WeightedRandomSampler:
    """
    Builds a WeightedRandomSampler so each epoch sees a balanced class distribution.
    Minority classes (DF, VASC, SCC) are oversampled relative to NV.
    """
    labels = dataset.labels
    class_counts = np.bincount(labels, minlength=len(ISIC2019_CLASSES))
    # Weight per class: inverse frequency
    class_weights = 1.0 / np.where(class_counts == 0, 1, class_counts)
    # Weight per sample
    sample_weights = torch.tensor([class_weights[lbl] for lbl in labels], dtype=torch.float)
    return WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(sample_weights),
        replacement=True,
    )


# ── DataLoader factory ────────────────────────────────────────────────────────

def get_dataloaders(
    train_csv: str | Path,
    val_csv: str | Path,
    test_csv: str | Path,
    img_dir: str | Path,
    batch_size: int = 32,
    img_size: int = 224,
    num_workers: int = 2,
    use_weighted_sampler: bool = True,
) -> dict[str, DataLoader]:
    """
    Returns {"train": DataLoader, "val": DataLoader, "test": DataLoader}.

    img_dir   : directory containing the raw .jpg images (e.g. Drive's
                ISIC_2019_Training_Input/). Passed to ISICDataset so image
                paths are reconstructed at runtime — not read from CSV.
    train loader uses WeightedRandomSampler by default (oversamples rare classes).
    val/test loaders are sequential (no shuffling, no oversampling).

    num_workers=2 is safe for Colab; set to 0 if you see DataLoader hangs.
    """
    train_ds = ISICDataset(train_csv, img_dir=img_dir, transform=get_train_transform(img_size))
    val_ds   = ISICDataset(val_csv,   img_dir=img_dir, transform=get_val_transform(img_size))
    test_ds  = ISICDataset(test_csv,  img_dir=img_dir, transform=get_val_transform(img_size))

    train_sampler = make_weighted_sampler(train_ds) if use_weighted_sampler else None

    train_loader = DataLoader(
        train_ds,
        batch_size=batch_size,
        sampler=train_sampler,
        shuffle=(train_sampler is None),   # mutually exclusive with sampler
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,                    # avoid tiny last batch issues with fp16
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )

    log.info(
        f"DataLoaders ready — "
        f"train: {len(train_ds):,} | val: {len(val_ds):,} | test: {len(test_ds):,} | "
        f"batch: {batch_size} | weighted_sampler: {use_weighted_sampler}"
    )
    return {"train": train_loader, "val": val_loader, "test": test_loader}
