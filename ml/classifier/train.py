"""
ml/classifier/train.py
======================
Colab-ready training script for ISIC 2019 skin lesion classifier.

LOCKED constraints (from PROJECT_STATUS.md):
  - EfficientNet-B0, 224x224, 8 classes
  - fp16 mixed precision (torch.cuda.amp)
  - Batch size 16-32 (default 32)
  - Max 10 epochs
  - Per-epoch checkpoint saved to Google Drive
  - --resume flag: restores weights + optimizer + scheduler + epoch + best metric
  - Dataset lives in Drive permanently (never re-downloaded)
  - Drive mount root: /content/drive/MyDrive/dermatology/

2-Phase fine-tuning:
  Phase A (epochs 1-3) : backbone frozen, head only, lr=1e-3
  Phase B (epochs 4-10): all layers, lr=1e-4

Run on Colab:
  !python ml/classifier/train.py \\
      --drive_root /content/drive/MyDrive/dermatology \\
      --epochs 10 \\
      --batch_size 32

Resume after disconnect:
  !python ml/classifier/train.py \\
      --drive_root /content/drive/MyDrive/dermatology \\
      --resume latest \\
      --epochs 10
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from ml.classifier.dataset import ISIC2019_CLASSES, get_dataloaders
from ml.classifier.model import build_model
from ml.utils.logger import get_logger

log = get_logger(__name__)

MEL_CLASS_IDX = ISIC2019_CLASSES.index("MEL")   # 0  — tracked separately every epoch


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train ISIC 2019 skin lesion classifier")

    p.add_argument("--drive_root", type=str,
                   default="/content/drive/MyDrive/dermatology",
                   help="Google Drive root containing dataset + checkpoints/")
    p.add_argument("--data_dir", type=str, default=None,
                   help="Override path to processed CSVs (default: <project_root>/data/processed/)")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch_size", type=int, default=32)
    p.add_argument("--lr_head", type=float, default=1e-3,
                   help="LR for Phase A (head-only, epochs 1-3)")
    p.add_argument("--lr_full", type=float, default=1e-4,
                   help="LR for Phase B (full model, epochs 4-10)")
    p.add_argument("--weight_decay", type=float, default=1e-4)
    p.add_argument("--num_workers", type=int, default=2)
    p.add_argument("--phase_b_start", type=int, default=4,
                   help="Epoch at which to unfreeze backbone (Phase B)")
    p.add_argument("--resume", type=str, default=None,
                   help="'latest' or path to a checkpoint .pt file to resume from")
    p.add_argument("--no_weighted_sampler", action="store_true",
                   help="Disable WeightedRandomSampler (use plain shuffling instead)")
    return p.parse_args()


# ── Colab / Drive setup ───────────────────────────────────────────────────────

def mount_drive_if_colab() -> bool:
    """Mount Google Drive if running in Colab. Returns True if mounted."""
    import os
    if os.path.exists("/content/drive/MyDrive"):
        log.info("Google Drive is already mounted.")
        return True
    try:
        import google.colab  # noqa: F401
        from google.colab import drive
        drive.mount("/content/drive")
        log.info("Google Drive mounted at /content/drive")
        return True
    except Exception as e:
        log.info(f"Skipping Drive mount: {e}")
        return False


def resolve_checkpoint_dir(drive_root: str) -> Path:
    ckpt_dir = Path(drive_root) / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    return ckpt_dir


def resolve_data_dir(drive_root: str, data_dir_override: str | None) -> Path:
    if data_dir_override:
        return Path(data_dir_override)
    # Default: <project_root>/data/processed/
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "data" / "processed"


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def save_checkpoint(
    ckpt_dir: Path,
    epoch: int,
    model: nn.Module,
    optimizer: AdamW,
    scheduler: CosineAnnealingLR,
    best_val_bal_acc: float,
    best_mel_recall: float,
    is_best: bool,
) -> None:
    state = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict(),
        "best_val_bal_acc": best_val_bal_acc,
        "best_mel_recall": best_mel_recall,
        "class_names": ISIC2019_CLASSES,
    }
    epoch_path = ckpt_dir / f"checkpoint_epoch_{epoch:02d}.pt"
    torch.save(state, epoch_path)
    log.info(f"  Checkpoint saved → {epoch_path}")

    if is_best:
        best_path = ckpt_dir / "best_model.pt"
        torch.save(state, best_path)
        log.info(f"  ★ Best model updated → {best_path}")


def load_checkpoint(resume: str, ckpt_dir: Path, device: torch.device) -> dict:
    """
    Load a checkpoint by path or 'latest'.
    Returns the raw state dict so caller can restore all components.
    """
    if resume == "latest":
        candidates = sorted(ckpt_dir.glob("checkpoint_epoch_*.pt"))
        if not candidates:
            log.warning("No checkpoints found in %s — starting from scratch.", ckpt_dir)
            return {}
        ckpt_path = candidates[-1]
    else:
        ckpt_path = Path(resume)
        if not ckpt_path.exists():
            sys.exit(f"[ERROR] Checkpoint not found: {ckpt_path}")

    log.info(f"Resuming from checkpoint: {ckpt_path}")
    return torch.load(ckpt_path, map_location=device)


# ── Class weights ─────────────────────────────────────────────────────────────

def compute_class_weight_tensor(train_csv: Path, device: torch.device) -> torch.Tensor:
    """Inverse-frequency weights from the training CSV."""
    import numpy as np
    import pandas as pd

    df = pd.read_csv(train_csv)
    counts = df["label"].value_counts().sort_index().values.astype(float)
    total = counts.sum()
    n_cls = len(ISIC2019_CLASSES)
    weights = total / (n_cls * counts)
    log.info("Class weights: " + " | ".join(
        f"{ISIC2019_CLASSES[i]}={weights[i]:.3f}" for i in range(n_cls)
    ))
    return torch.tensor(weights, dtype=torch.float32).to(device)


# ── Training / validation loops ───────────────────────────────────────────────

def run_epoch(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    optimizer: AdamW | None,
    scaler: GradScaler,
    device: torch.device,
    is_train: bool,
) -> tuple[float, float, dict]:
    """
    Single epoch pass. Returns (avg_loss, accuracy, per_class_correct_dict).
    optimizer=None for validation.
    """
    model.train() if is_train else model.eval()

    total_loss = 0.0
    correct = 0
    total = 0
    class_correct = [0] * len(ISIC2019_CLASSES)
    class_total   = [0] * len(ISIC2019_CLASSES)
    mel_tn = 0
    mel_fp = 0

    ctx = torch.enable_grad() if is_train else torch.no_grad()
    with ctx:
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)

            with autocast():
                logits = model(images)
                loss = criterion(logits, labels)

            if is_train:
                optimizer.zero_grad()
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

            preds = logits.argmax(dim=1)
            correct += (preds == labels).sum().item()
            total   += labels.size(0)
            total_loss += loss.item() * labels.size(0)

            for i in range(len(ISIC2019_CLASSES)):
                mask = labels == i
                class_correct[i] += (preds[mask] == labels[mask]).sum().item()
                class_total[i]   += mask.sum().item()
                
            non_mel_mask = labels != MEL_CLASS_IDX
            mel_tn += (preds[non_mel_mask] != MEL_CLASS_IDX).sum().item()
            mel_fp += (preds[non_mel_mask] == MEL_CLASS_IDX).sum().item()

    avg_loss = total_loss / total
    accuracy = correct / total
    per_class_recall = {
        ISIC2019_CLASSES[i]: (class_correct[i] / class_total[i] if class_total[i] > 0 else 0.0)
        for i in range(len(ISIC2019_CLASSES))
    }
    bal_acc = sum(per_class_recall.values()) / len(ISIC2019_CLASSES)
    mel_spec = mel_tn / (mel_tn + mel_fp) if (mel_tn + mel_fp) > 0 else 0.0
    return avg_loss, bal_acc, per_class_recall, mel_spec


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # 1. Mount Drive if on Colab
    mount_drive_if_colab()

    ckpt_dir  = resolve_checkpoint_dir(args.drive_root)
    data_dir  = resolve_data_dir(args.drive_root, args.data_dir)
    log_csv   = Path(args.drive_root) / "training_log.csv"

    train_csv = data_dir / "train.csv"
    val_csv   = data_dir / "val.csv"
    test_csv  = data_dir / "test.csv"

    for f in [train_csv, val_csv, test_csv]:
        if not f.exists():
            sys.exit(f"[ERROR] Required file not found: {f}\n"
                     f"  → Run data/prepare_dataset.py first.")

    # Image directory: where the raw .jpg files live on Drive
    img_dir = Path(args.drive_root) / "ISIC_2019_Training_Input"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Device: {device}")

    # 2. DataLoaders
    loaders = get_dataloaders(
        train_csv=train_csv,
        val_csv=val_csv,
        test_csv=test_csv,
        img_dir=img_dir,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        use_weighted_sampler=not args.no_weighted_sampler,
    )

    # 3. Model
    model = build_model().to(device)

    # 4. Loss with class weights
    class_weights = compute_class_weight_tensor(train_csv, device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    # 5. Optimizer + scheduler (Phase A defaults)
    model.freeze_backbone()
    optimizer = AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr_head,
        weight_decay=args.weight_decay,
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)
    scaler    = GradScaler()

    # 6. Resume from checkpoint if requested
    start_epoch   = 1
    best_val_bal_acc  = 0.0
    best_mel_recall = 0.0

    if args.resume:
        ckpt = load_checkpoint(args.resume, ckpt_dir, device)
        if ckpt:
            model.load_state_dict(ckpt["model_state_dict"])
            optimizer.load_state_dict(ckpt["optimizer_state_dict"])
            scheduler.load_state_dict(ckpt["scheduler_state_dict"])
            start_epoch     = ckpt["epoch"] + 1
            best_val_bal_acc    = ckpt.get("best_val_bal_acc", 0.0)
            best_mel_recall = ckpt.get("best_mel_recall", 0.0)
            log.info(f"Resumed from epoch {ckpt['epoch']} | "
                     f"best_val_bal_acc={best_val_bal_acc:.4f} | best_mel_recall={best_mel_recall:.4f}")

            # Restore correct phase
            if start_epoch >= args.phase_b_start:
                log.info("Restoring Phase B (full model) optimizer LR")
                model.unfreeze_all()
                for pg in optimizer.param_groups:
                    pg["lr"] = args.lr_full

    # 7. Training log CSV header
    log_exists = log_csv.exists()
    log_file = open(log_csv, "a", newline="")
    log_writer = csv.writer(log_file)
    if not log_exists:
        log_writer.writerow([
            "epoch", "phase",
            "train_loss", "train_bal_acc",
            "val_loss", "val_bal_acc",
            "mel_recall", "mel_spec", "lr",
        ])

    # 8. Epoch loop
    log.info(f"\n{'='*60}")
    log.info(f"Training EfficientNet-B0 | epochs {start_epoch}-{args.epochs}")
    log.info(f"Checkpoints → {ckpt_dir}")
    log.info(f"{'='*60}")

    for epoch in range(start_epoch, args.epochs + 1):
        t0 = time.time()

        # Phase transition
        if epoch == args.phase_b_start:
            log.info(f"\n>>> Phase B: unfreezing backbone (epoch {epoch})")
            model.unfreeze_all()
            for pg in optimizer.param_groups:
                pg["lr"] = args.lr_full

        phase = "A" if epoch < args.phase_b_start else "B"
        current_lr = optimizer.param_groups[0]["lr"]

        # Train
        train_loss, train_bal_acc, _, _ = run_epoch(
            model, loaders["train"], criterion, optimizer, scaler, device, is_train=True
        )
        scheduler.step()

        # Validate
        val_loss, val_bal_acc, val_recall, val_mel_spec = run_epoch(
            model, loaders["val"], criterion, None, scaler, device, is_train=False
        )
        mel_recall = val_recall["MEL"]
        elapsed = time.time() - t0

        # Log
        log.info(
            f"Epoch {epoch:02d}/{args.epochs} [Ph{phase}] "
            f"| train_loss={train_loss:.4f} bal_acc={train_bal_acc:.4f} "
            f"| val_loss={val_loss:.4f} bal_acc={val_bal_acc:.4f} "
            f"| MEL_rec={mel_recall:.4f} MEL_spec={val_mel_spec:.4f} "
            f"| lr={current_lr:.2e} | {elapsed:.0f}s"
        )
        log_writer.writerow([
            epoch, phase,
            f"{train_loss:.4f}", f"{train_bal_acc:.4f}",
            f"{val_loss:.4f}", f"{val_bal_acc:.4f}",
            f"{mel_recall:.4f}", f"{val_mel_spec:.4f}", f"{current_lr:.2e}",
        ])
        log_file.flush()

        # Primary save metric: MEL recall if spec>=0.5 and bal_acc>=0.5
        # Secondary: val balanced accuracy
        is_best = False
        if val_mel_spec >= 0.50 and val_bal_acc >= 0.50:
            if mel_recall > best_mel_recall:
                is_best = True
                best_mel_recall = mel_recall
                best_val_bal_acc = val_bal_acc
        else:
            if val_bal_acc > best_val_bal_acc:
                is_best = True
                best_val_bal_acc = val_bal_acc

        # Per-epoch checkpoint → Drive
        save_checkpoint(
            ckpt_dir, epoch, model, optimizer, scheduler,
            best_val_bal_acc, best_mel_recall, is_best,
        )

        # Warn if MEL recall is dangerously low
        if mel_recall < 0.70:
            log.warning(f"  ⚠️  MEL recall={mel_recall:.4f} below 0.70 — model may miss melanomas")

    log_file.close()
    log.info(f"\n✅ Training complete.")
    log.info(f"   Best val bal_acc  : {best_val_bal_acc:.4f}")
    log.info(f"   Best MEL recall   : {best_mel_recall:.4f}")
    log.info(f"   Checkpoints saved : {ckpt_dir}")
    log.info(f"   Training log      : {log_csv}")


if __name__ == "__main__":
    main()
