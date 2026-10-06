"""
ml/classifier/calibration.py
============================
Two post-hoc calibration / safety utilities:

1. OOD (Out-Of-Distribution) gate
   --------------------------------
   Uses max-softmax probability AND energy score computed from raw logits.
   Stats (mean/std of val-set max-softmax and energy) are stored in
   ml/classifier/ood_stats.json (path key from agent/config.OOD_STATS_JSON).

   fit_ood_stats(model, val_loader, device, out_path)
       -> computes and saves val-set distribution statistics.

   is_ood(logits_or_probs, ood_stats) -> bool
       -> returns True if the image looks non-skin (OOD).

2. Temperature scaling
   --------------------
   A single scalar T fitted on the val set by minimising NLL.
   Saved to ml/classifier/temperature.json (agent/config.TEMPERATURE_JSON).

   fit_temperature(model, val_loader, device, out_path) -> float
   apply_temperature(logits, temperature) -> torch.Tensor  (calibrated probs)
   load_temperature(path) -> float

3. ECE (Expected Calibration Error)
   -----------------------------------
   compute_ece(probs, labels, n_bins=15) -> float
       Added to evaluate.py output.

Run fitting on Colab after training:
    python -m ml.classifier.calibration \\
        --checkpoint /content/drive/.../best_model.pt \\
        --drive_root  /content/drive/MyDrive/dermatology
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

log = logging.getLogger(__name__)

# -- project-root sys.path fix (needed when run as __main__) ------------------
import sys, os
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.config import (
    OOD_MAX_SOFTMAX_THRESHOLD,
    OOD_ENERGY_THRESHOLD,
)

# -----------------------------------------------------------------------------
# 1.  OOD gate
# -----------------------------------------------------------------------------

@torch.no_grad()
def fit_ood_stats(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    out_path: str | Path,
) -> dict:
    """
    Compute max-softmax and energy-score statistics over the validation set.
    Saves a JSON file and returns the stats dict.

    Stats dict schema:
    {
        "max_softmax_mean": float,
        "max_softmax_std":  float,
        "energy_mean":      float,
        "energy_std":       float,
        "n_samples":        int,
    }
    """
    model.eval()
    max_softmaxes, energies = [], []

    for images, _ in val_loader:
        images = images.to(device)
        logits = model(images)                        # (B, C)
        probs  = F.softmax(logits, dim=1)
        max_softmaxes.append(probs.max(dim=1).values.cpu().numpy())
        # Energy score: -log(sum(exp(logits)))
        energy = -torch.logsumexp(logits, dim=1).cpu().numpy()
        energies.append(energy)

    ms_arr = np.concatenate(max_softmaxes)
    en_arr = np.concatenate(energies)

    stats = {
        "max_softmax_mean": float(ms_arr.mean()),
        "max_softmax_std":  float(ms_arr.std()),
        "energy_mean":      float(en_arr.mean()),
        "energy_std":       float(en_arr.std()),
        "n_samples":        int(len(ms_arr)),
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(stats, indent=2))
    log.info("OOD stats saved -> %s  (n=%d)", out_path, stats["n_samples"])
    return stats


def load_ood_stats(path: str | Path) -> dict:
    """Load previously fitted OOD stats from JSON."""
    return json.loads(Path(path).read_text())


def is_ood(
    logits: torch.Tensor,
    ood_stats: Optional[dict] = None,
) -> bool:
    """
    Returns True if the image is likely Out-Of-Distribution (not a skin lesion).

    Decision rule (either condition alone is sufficient):
      A. max-softmax < OOD_MAX_SOFTMAX_THRESHOLD
      B. energy score > OOD_ENERGY_THRESHOLD   (less negative = more OOD)

    logits: 1D or (1, C) tensor of raw model logits.
    ood_stats: optional -- if provided, also flags inputs whose max-softmax is
               more than 3 std-devs below the val-set mean (distribution shift).
    """
    if logits.dim() == 1:
        logits = logits.unsqueeze(0)

    probs      = F.softmax(logits, dim=1)
    max_prob   = float(probs.max())
    energy     = float(-torch.logsumexp(logits, dim=1))

    if max_prob < OOD_MAX_SOFTMAX_THRESHOLD:
        return True

    if energy > OOD_ENERGY_THRESHOLD:
        return True

    if ood_stats is not None:
        # Distribution-shift check: 3-sigma rule on val-set max-softmax
        ms_mean = ood_stats["max_softmax_mean"]
        ms_std  = ood_stats["max_softmax_std"]
        if max_prob < ms_mean - 3 * ms_std:
            return True

    return False


# -----------------------------------------------------------------------------
# 2.  Temperature scaling
# -----------------------------------------------------------------------------

class _TemperatureScaler(nn.Module):
    """Single-parameter wrapper used only during fitting."""
    def __init__(self):
        super().__init__()
        self.temperature = nn.Parameter(torch.ones(1) * 1.5)

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        return logits / self.temperature.clamp(min=0.05)


@torch.no_grad()
def _collect_logits_labels(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor]:
    model.eval()
    all_logits, all_labels = [], []
    for images, labels in loader:
        images = images.to(device)
        logits = model(images).cpu()
        all_logits.append(logits)
        all_labels.append(labels)
    return torch.cat(all_logits), torch.cat(all_labels)


def fit_temperature(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    out_path: str | Path,
    lr: float = 0.01,
    max_iter: int = 50,
) -> float:
    """
    Fit a single temperature scalar on val-set logits (minimise NLL).
    Saves result to JSON and returns the temperature value.
    """
    log.info("Collecting val-set logits for temperature fitting ...")
    logits, labels = _collect_logits_labels(model, val_loader, device)

    scaler    = _TemperatureScaler()
    criterion = nn.CrossEntropyLoss()
    optimiser = torch.optim.LBFGS([scaler.temperature], lr=lr, max_iter=max_iter)

    def _eval():
        optimiser.zero_grad()
        loss = criterion(scaler(logits), labels)
        loss.backward()
        return loss

    optimiser.step(_eval)
    temperature = float(scaler.temperature.item())

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"temperature": temperature}, indent=2))
    log.info("Temperature fitted: %.4f  -> saved to %s", temperature, out_path)
    return temperature


def load_temperature(path: str | Path) -> float:
    """Load fitted temperature from JSON. Returns 1.0 if file not found."""
    p = Path(path)
    if not p.exists():
        log.warning("temperature.json not found at %s -- using T=1.0", p)
        return 1.0
    return float(json.loads(p.read_text())["temperature"])


def apply_temperature(
    logits: torch.Tensor,
    temperature: float,
) -> torch.Tensor:
    """Return calibrated softmax probabilities for given logits."""
    return F.softmax(logits / max(temperature, 1e-4), dim=-1)


# -----------------------------------------------------------------------------
# 3.  Expected Calibration Error (ECE)
# -----------------------------------------------------------------------------

def compute_ece(
    probs: np.ndarray,
    labels: np.ndarray,
    n_bins: int = 15,
) -> float:
    """
    Compute multi-class Expected Calibration Error.

    Parameters
    ----------
    probs  : (N, C) softmax probabilities
    labels : (N,)  integer class labels
    n_bins : number of equal-width confidence bins

    Returns
    -------
    float -- ECE in [0, 1]
    """
    max_probs = probs.max(axis=1)
    preds     = probs.argmax(axis=1)
    correct   = (preds == labels).astype(float)

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece  = 0.0
    n    = len(labels)

    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (max_probs >= lo) & (max_probs < hi)
        if not mask.any():
            continue
        bin_conf = max_probs[mask].mean()
        bin_acc  = correct[mask].mean()
        ece     += mask.sum() / n * abs(bin_acc - bin_conf)

    return float(ece)


# -----------------------------------------------------------------------------
# CLI -- fit both on val set
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fit OOD stats + temperature on val set")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--drive_root", default="/content/drive/MyDrive/dermatology")
    parser.add_argument("--data_dir",   default=None)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--num_workers", type=int, default=2)
    args = parser.parse_args()

    from ml.classifier.model   import build_model
    from ml.classifier.dataset import get_dataloaders

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    drive_root   = Path(args.drive_root)
    ckpt_path    = drive_root / "checkpoints" / args.checkpoint
    project_root = Path(__file__).resolve().parents[2]
    data_dir     = Path(args.data_dir) if args.data_dir else project_root / "data" / "processed"
    img_dir      = drive_root / "ISIC_2019_Training_Input"

    model = build_model().to(device)
    ckpt  = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    loaders = get_dataloaders(
        train_csv=data_dir / "train.csv",
        val_csv=data_dir / "val.csv",
        test_csv=data_dir / "test.csv",
        img_dir=img_dir,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        use_weighted_sampler=False,
    )

    out_dir = Path(__file__).parent
    fit_ood_stats(model, loaders["val"], device, out_dir / "ood_stats.json")
    fit_temperature(model, loaders["val"], device, out_dir / "temperature.json")

    print("Done. Files written to", out_dir)
