"""
ml/classifier/predict.py
========================
Single-image inference entry point.
Called by the FastAPI backend (/api/diagnosis) and Grad-CAM CLI.

Returns a structured dict with:
  - predicted class and confidence
  - all 8 class probabilities
  - optional Grad-CAM heatmap PNG path

Usage (programmatic):
    from ml.classifier.predict import load_model, predict
    model, device = load_model("/content/drive/MyDrive/dermatology/checkpoints/best_model.pt")
    result = predict("path/to/image.jpg", model, device, save_gradcam=True)

Usage (CLI):
    python ml/classifier/predict.py \\
        --image path/to/image.jpg \\
        --checkpoint /content/drive/MyDrive/dermatology/checkpoints/best_model.pt \\
        --gradcam
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from ml.classifier.dataset import ISIC2019_CLASSES, get_val_transform
from ml.classifier.model import build_model
from ml.utils.logger import get_logger
from ml.classifier.calibration import (
    apply_temperature,
    is_ood,
    load_ood_stats,
    load_temperature,
)

log = get_logger(__name__)

# -- Load calibration artefacts at import time (graceful: files may not yet exist) --
_CAL_DIR = Path(__file__).parent
_TEMPERATURE: float = load_temperature(_CAL_DIR / "temperature.json")
try:
    _OOD_STATS: dict | None = load_ood_stats(_CAL_DIR / "ood_stats.json")
except FileNotFoundError:
    _OOD_STATS = None
    log.warning("ood_stats.json not found -- OOD 3-sigma check disabled")

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

MEL_IDX = ISIC2019_CLASSES.index("MEL")
HIGH_RISK_CLASSES = {"MEL", "BCC", "SCC"}   # trigger urgency flag


# ── Model loading ─────────────────────────────────────────────────────────────

def load_model(
    checkpoint_path: str | Path,
    device: Optional[torch.device] = None,
) -> tuple:
    """
    Load EfficientNet-B0 from a checkpoint.
    Returns (model, device).
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    ckpt_path = Path(checkpoint_path)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    model = build_model(pretrained=False)   # no re-download; weights come from checkpoint
    ckpt  = torch.load(ckpt_path, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()

    log.info(f"Model loaded from {ckpt_path} (epoch {ckpt.get('epoch', '?')})")
    return model, device


# ── Preprocessing ─────────────────────────────────────────────────────────────

def preprocess_image(image_input: str | Path | Image.Image) -> torch.Tensor:
    """
    Accepts a file path or a PIL Image.
    Returns a (1, 3, 224, 224) tensor ready for inference.
    """
    transform = get_val_transform(img_size=224)
    if isinstance(image_input, (str, Path)):
        img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, Image.Image):
        img = image_input.convert("RGB")
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")
    return transform(img).unsqueeze(0)   # add batch dim


# ── Grad-CAM ──────────────────────────────────────────────────────────────────

def generate_gradcam(
    model,
    input_tensor: torch.Tensor,
    predicted_class_idx: int,
    original_image: Image.Image,
    device: torch.device,
    output_path: str | Path,
) -> str:
    """
    Generates a Grad-CAM heatmap overlay and saves it as a PNG.
    Requires: pip install grad-cam

    Returns the path to the saved PNG.
    """
    try:
        from pytorch_grad_cam import GradCAM
        from pytorch_grad_cam.utils.image import show_cam_on_image
    except ImportError:
        log.warning("grad-cam not installed. Run: pip install grad-cam")
        return ""

    target_layer = [model.get_gradcam_target_layer()]

    cam = GradCAM(model=model, target_layers=target_layer)

    # GradCAM needs fp32 input
    input_fp32 = input_tensor.float().to(device)

    # Use predicted class as target (None = top predicted class)
    grayscale_cam = cam(input_tensor=input_fp32, targets=None)
    grayscale_cam = grayscale_cam[0]   # (H, W)

    # Prepare original image as float numpy array [0,1]
    img_resized = original_image.resize((224, 224))
    img_np = np.array(img_resized).astype(np.float32) / 255.0

    # Overlay heatmap
    visualization = show_cam_on_image(img_np, grayscale_cam, use_rgb=True)
    result_img = Image.fromarray(visualization)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result_img.save(out_path)
    log.info(f"Grad-CAM saved → {out_path}")
    return str(out_path)


# ── Core predict function ─────────────────────────────────────────────────────

@torch.no_grad()
def predict(
    image_input: str | Path | Image.Image,
    model,
    device: torch.device,
    save_gradcam: bool = False,
    gradcam_output_path: Optional[str] = None,
) -> dict:
    """
    Run inference on a single image.

    Args:
        image_input        : file path, Path, or PIL.Image
        model              : loaded SkinLesionClassifier (from load_model)
        device             : torch.device
        save_gradcam       : if True, generate and save Grad-CAM overlay
        gradcam_output_path: where to save the PNG (default: system temp dir)

    Returns:
        {
            "predicted_class":   "MEL",
            "predicted_label":   0,
            "confidence":        0.87,
            "description":       "Melanoma",
            "is_high_risk":      True,
            "all_probabilities": {"MEL": 0.87, "NV": 0.06, ...},
            "gradcam_path":      "/tmp/gradcam_abc.png"  or None
        }
    """
    # Load original image for Grad-CAM overlay
    if isinstance(image_input, (str, Path)):
        original_pil = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, Image.Image):
        original_pil = image_input.convert("RGB")
    else:
        raise TypeError(f"Unsupported type: {type(image_input)}")

    input_tensor = preprocess_image(original_pil).to(device)

    model.eval()
    with torch.no_grad():
        logits = model(input_tensor)                  # keep raw logits

    # -- OOD gate: reject non-skin images before any classification -------
    if is_ood(logits.squeeze(), ood_stats=_OOD_STATS):
        return {
            "ood_rejected": True,
            "predicted_class":   None,
            "predicted_label":   None,
            "confidence":        None,
            "description":       None,
            "is_high_risk":      False,
            "all_probabilities": {},
            "gradcam_path":      None,
        }

    # -- Temperature-scaled probabilities ---------------------------------
    probs = apply_temperature(logits, _TEMPERATURE).squeeze().cpu().numpy()

    pred_idx = int(probs.argmax())
    pred_class = ISIC2019_CLASSES[pred_idx]
    confidence = float(probs[pred_idx])

    all_probs = {cls: round(float(probs[i]), 4) for i, cls in enumerate(ISIC2019_CLASSES)}

    # Grad-CAM (optional)
    gradcam_path = None
    if save_gradcam:
        if gradcam_output_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False, prefix="gradcam_")
            gradcam_output_path = tmp.name
            tmp.close()
        gradcam_path = generate_gradcam(
            model=model,
            input_tensor=input_tensor,
            predicted_class_idx=pred_idx,
            original_image=original_pil,
            device=device,
            output_path=gradcam_output_path,
        )

    result = {
        "ood_rejected":      False,
        "predicted_class":   pred_class,
        "predicted_label":   pred_idx,
        "confidence":        round(confidence, 4),
        "description":       CLASS_DESCRIPTIONS[pred_class],
        "is_high_risk":      pred_class in HIGH_RISK_CLASSES,
        "all_probabilities": all_probs,
        "gradcam_path":      gradcam_path,
    }
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Single-image skin lesion prediction")
    p.add_argument("--image", required=True, help="Path to input image")
    p.add_argument("--checkpoint", required=True, help="Path to best_model.pt")
    p.add_argument("--gradcam", action="store_true", help="Generate Grad-CAM overlay")
    p.add_argument("--gradcam_out", type=str, default=None,
                   help="Output path for Grad-CAM PNG (default: temp file)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not Path(args.image).exists():
        sys.exit(f"[ERROR] Image not found: {args.image}")

    model, device = load_model(args.checkpoint)
    result = predict(
        image_input=args.image,
        model=model,
        device=device,
        save_gradcam=args.gradcam,
        gradcam_output_path=args.gradcam_out,
    )

    print("\n" + "=" * 50)
    print("Prediction Result")
    print("=" * 50)
    print(json.dumps(result, indent=2))
    if result.get("is_high_risk"):
        print(f"\n⚠️  HIGH RISK CLASS DETECTED: {result['predicted_class']}")
        print("   Recommend urgent dermatologist review.")
