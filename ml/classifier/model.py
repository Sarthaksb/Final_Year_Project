"""
ml/classifier/model.py
======================
EfficientNet-B0 fine-tuned for ISIC 2019 skin lesion classification.

Architecture:
  - Backbone : timm EfficientNet-B0, pretrained on ImageNet-1k
  - Head     : Dropout(0.3) → Linear(1280, 8)
  - Input    : 224×224 RGB

2-Phase fine-tuning:
  Phase A (epochs 1-3) : backbone frozen, head-only training
  Phase B (epochs 4-10): full model, lower LR
"""

import timm
import torch
import torch.nn as nn

ISIC2019_CLASSES = ["MEL", "NV", "BCC", "AK", "BKL", "DF", "VASC", "SCC"]
NUM_CLASSES = len(ISIC2019_CLASSES)   # 8
EFFICIENTNET_FEATURE_DIM = 1280       # B0 penultimate feature dimension


class SkinLesionClassifier(nn.Module):
    """
    EfficientNet-B0 with a custom classification head for 8-class skin lesion detection.
    """

    def __init__(self, num_classes: int = NUM_CLASSES, dropout: float = 0.3, pretrained: bool = True):
        super().__init__()
        # Load backbone without the default head (num_classes=0 → identity)
        self.backbone = timm.create_model(
            "efficientnet_b0",
            pretrained=pretrained,
            num_classes=0,          # removes default classifier
            global_pool="avg",      # global average pooling after conv_head
        )
        self.head = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(EFFICIENTNET_FEATURE_DIM, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)   # (B, 1280)
        return self.head(features)    # (B, 8)

    # ── Fine-tuning phase helpers ─────────────────────────────────────────────

    def freeze_backbone(self) -> None:
        """Phase A: only train the head."""
        for param in self.backbone.parameters():
            param.requires_grad = False
        for param in self.head.parameters():
            param.requires_grad = True

    def unfreeze_all(self) -> None:
        """Phase B: train the full model end-to-end."""
        for param in self.parameters():
            param.requires_grad = True

    def get_gradcam_target_layer(self) -> nn.Module:
        """Return the last convolutional layer for Grad-CAM hooks."""
        return self.backbone.conv_head


def build_model(
    num_classes: int = NUM_CLASSES,
    dropout: float = 0.3,
    pretrained: bool = True,
) -> SkinLesionClassifier:
    """Factory function — use this everywhere instead of instantiating directly."""
    return SkinLesionClassifier(num_classes=num_classes, dropout=dropout, pretrained=pretrained)


if __name__ == "__main__":
    # Quick sanity check
    model = build_model()
    dummy = torch.randn(2, 3, 224, 224)
    out = model(dummy)
    print(f"Output shape: {out.shape}")   # Expected: torch.Size([2, 8])
    print("model.py OK")
