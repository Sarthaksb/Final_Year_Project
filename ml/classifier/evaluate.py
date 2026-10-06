"""
ml/classifier/evaluate.py
=========================
Evaluation script for the trained ISIC 2019 classifier.

Loads best_model.pt from Drive checkpoints/, runs on the test set, and produces:
  - evaluation_report.txt   : full text metrics
  - confusion_matrix.png    : heatmap (saved to Drive)
  - roc_curves.png          : per-class AUC curves (saved to Drive)

Metrics reported:
  - Overall accuracy
  - Macro + weighted precision, recall, F1
  - Per-class precision, recall, F1, support
  - ★ MEL recall flagged separately (safety-critical)
  - ROC-AUC per class (one-vs-rest)

Run on Colab:
  !python ml/classifier/evaluate.py \\
      --drive_root /content/drive/MyDrive/dermatology \\
      --checkpoint best_model.pt
"""

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import torch
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from torch.cuda.amp import autocast

from ml.classifier.dataset import ISIC2019_CLASSES, get_dataloaders
from ml.classifier.model import build_model
from ml.classifier.calibration import compute_ece
from ml.utils.logger import get_logger

log = get_logger(__name__)

MEL_IDX = ISIC2019_CLASSES.index("MEL")
MEL_RECALL_THRESHOLD = 0.80   # minimum acceptable for clinical use


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate ISIC 2019 classifier on test set")
    p.add_argument("--drive_root", type=str,
                   default="/content/drive/MyDrive/dermatology")
    p.add_argument("--data_dir", type=str, default=None,
                   help="Path to processed CSVs (default: <project_root>/data/processed/)")
    p.add_argument("--checkpoint", type=str, default="best_model.pt",
                   help="Checkpoint filename inside <drive_root>/checkpoints/")
    p.add_argument("--batch_size", type=int, default=32)
    p.add_argument("--num_workers", type=int, default=2)
    return p.parse_args()


# ── Inference ─────────────────────────────────────────────────────────────────

@torch.no_grad()
def run_inference(model, loader, device) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (all_labels, all_preds, all_probs).
    all_probs shape: (N, num_classes) — softmax probabilities for AUC.
    """
    model.eval()
    all_labels, all_preds, all_probs = [], [], []

    for images, labels in loader:
        images = images.to(device)
        with autocast():
            logits = model(images)
        probs = torch.softmax(logits, dim=1).cpu().numpy()
        preds = probs.argmax(axis=1)

        all_labels.extend(labels.numpy())
        all_preds.extend(preds)
        all_probs.append(probs)

    return (
        np.array(all_labels),
        np.array(all_preds),
        np.vstack(all_probs),
    )


# ── Plots ─────────────────────────────────────────────────────────────────────

def plot_confusion_matrix(y_true, y_pred, out_path: Path) -> None:
    cm = confusion_matrix(y_true, y_pred)
    # Normalize to recall (row-normalized)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    for ax, data, fmt, title in zip(
        axes,
        [cm, cm_norm],
        ["d", ".2f"],
        ["Confusion Matrix (counts)", "Confusion Matrix (recall-normalized)"],
    ):
        sns.heatmap(
            data, annot=True, fmt=fmt, cmap="Blues",
            xticklabels=ISIC2019_CLASSES,
            yticklabels=ISIC2019_CLASSES,
            ax=ax,
        )
        ax.set_title(title, fontsize=13)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")

    # Highlight MEL row
    for ax in axes:
        ax.get_yticklabels()[MEL_IDX].set_color("red")
        ax.get_yticklabels()[MEL_IDX].set_fontweight("bold")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"Confusion matrix saved → {out_path}")


def plot_roc_curves(y_true, y_probs, out_path: Path) -> dict[str, float]:
    """Plot one-vs-rest ROC curves. Returns dict of {class: AUC}."""
    n_classes = len(ISIC2019_CLASSES)
    y_true_bin = np.eye(n_classes)[y_true]   # one-hot

    fig, ax = plt.subplots(figsize=(10, 8))
    auc_scores = {}

    colors = plt.cm.tab10(np.linspace(0, 1, n_classes))
    for i, (cls, color) in enumerate(zip(ISIC2019_CLASSES, colors)):
        fpr, tpr, _ = roc_curve(y_true_bin[:, i], y_probs[:, i])
        auc = roc_auc_score(y_true_bin[:, i], y_probs[:, i])
        auc_scores[cls] = round(auc, 4)
        lw = 2.5 if cls == "MEL" else 1.2
        ls = "-" if cls == "MEL" else "--"
        label = f"{'★ ' if cls=='MEL' else ''}{cls} (AUC={auc:.3f})"
        ax.plot(fpr, tpr, lw=lw, ls=ls, color=color, label=label)

    ax.plot([0, 1], [0, 1], "k:", lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate (Recall)")
    ax.set_title("ROC Curves — ISIC 2019 Test Set\n(★ MEL = Melanoma, safety-critical)")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    log.info(f"ROC curves saved → {out_path}")
    return auc_scores


# ── Report ────────────────────────────────────────────────────────────────────

def build_report(
    y_true, y_pred, y_probs,
    auc_scores: dict,
    out_path: Path,
    ece: float = 0.0,
) -> None:
    report = classification_report(
        y_true, y_pred,
        target_names=ISIC2019_CLASSES,
        digits=4,
    )

    overall_acc = (y_true == y_pred).mean()
    mel_recall = (
        (y_pred[y_true == MEL_IDX] == MEL_IDX).mean()
        if (y_true == MEL_IDX).any() else 0.0
    )

    mel_flag = (
        "✅ PASS (≥0.80)" if mel_recall >= MEL_RECALL_THRESHOLD
        else f"⚠️  FAIL (<0.80) — model may miss melanomas in production"
    )

    lines = [
        "=" * 65,
        "ISIC 2019 Classifier -- Test Set Evaluation",
        "=" * 65,
        f"Overall Accuracy : {overall_acc:.4f}",
        f"ECE (calibration) : {ece:.4f}  (lower is better; 0 = perfect)",
        "",
        f"* Melanoma (MEL) Recall : {mel_recall:.4f}  ->  {mel_flag}",
        "  (Threshold: 0.80 -- missing melanoma = life-threatening false negative)",
        "",
        "-" * 65,
        "Per-Class Classification Report:",
        "-" * 65,
        report,
        "-" * 65,
        "ROC-AUC (one-vs-rest, per class):",
        "-" * 65,
    ]
    for cls in ISIC2019_CLASSES:
        prefix = "  ★" if cls == "MEL" else "   "
        lines.append(f"{prefix} {cls:<6}  AUC = {auc_scores.get(cls, 0.0):.4f}")

    lines += [
        "",
        "=" * 65,
        "Output files:",
        "  evaluation_report.txt",
        "  confusion_matrix.png",
        "  roc_curves.png",
        "=" * 65,
    ]

    text = "\n".join(lines)
    print(text)
    out_path.write_text(text, encoding="utf-8")
    log.info(f"Evaluation report saved → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    drive_root = Path(args.drive_root)
    ckpt_path  = drive_root / "checkpoints" / args.checkpoint
    out_dir    = drive_root / "evaluation"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not ckpt_path.exists():
        sys.exit(f"[ERROR] Checkpoint not found: {ckpt_path}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Device: {device} | Checkpoint: {ckpt_path}")

    # Data
    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = Path(args.data_dir) if args.data_dir else project_root / "data" / "processed"
    # Image directory: where the raw .jpg files live on Drive
    img_dir = drive_root / "ISIC_2019_Training_Input"
    loaders = get_dataloaders(
        train_csv=data_dir / "train.csv",
        val_csv=data_dir / "val.csv",
        test_csv=data_dir / "test.csv",
        img_dir=img_dir,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        use_weighted_sampler=False,   # eval: no oversampling
    )

    # Model
    model = build_model().to(device)
    ckpt = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    log.info(f"Loaded checkpoint from epoch {ckpt.get('epoch', '?')}")

    # Inference on test set
    log.info("Running inference on test set ...")
    y_true, y_pred, y_probs = run_inference(model, loaders["test"], device)

    # ECE
    ece = compute_ece(y_probs, y_true)
    log.info("ECE = %.4f", ece)

    # Plots
    plot_confusion_matrix(y_true, y_pred, out_dir / "confusion_matrix.png")
    auc_scores = plot_roc_curves(y_true, y_probs, out_dir / "roc_curves.png")

    # Report
    build_report(y_true, y_pred, y_probs, auc_scores, out_dir / "evaluation_report.txt", ece=ece)


if __name__ == "__main__":
    main()
