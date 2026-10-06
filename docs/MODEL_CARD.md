# DermaAI Model Card

## Model Overview
- **Name**: DermaAI Triage Classifier (EfficientNet-B0)
- **Architecture**: EfficientNet-B0 with a multi-head attention pooling layer, followed by a linear classification head.
- **Task**: Multi-class skin lesion classification (8 classes: MEL, NV, BCC, AK, BKL, DF, VASC, SCC).

## Intended Use
- **Primary Use Case**: As an AI-assisted triage system for early skin lesion evaluation.
- **Out of Scope**: NOT intended for definitive diagnosis. It acts strictly as clinical decision support. The product never overrides a doctor’s professional judgment.

## Training Data
- **Dataset**: ISIC 2019 Training Data (approx. 25,331 dermoscopic images).
- **Class Imbalance**: Highly imbalanced, with Melanocytic Nevi (NV) heavily represented. A weighted random sampler and focal loss were used during training to counteract class imbalance.

## Known Limitations
- **Dermoscopy vs. Phone-Photo Gap**: The model is trained almost entirely on dermoscopic images (captured with professional clinical equipment), but end users will upload standard smartphone photos. This distribution shift causes lower real-world accuracy and confidence compared to validation metrics.
- **Skin-Tone Bias**: The ISIC dataset predominantly features lighter skin tones (Fitzpatrick types I-III). The model has not been sufficiently validated on darker skin types (types IV-VI) and may perform poorly or produce skewed confidence scores on diverse populations.
- **OOD Handling**: Extremely noisy, out-of-focus, or non-skin images can confuse the model. A Laplacian variance check and OOD (Out-Of-Distribution) gating logic have been added to reject non-images.

## Failure Cases
- **Low Confidence on Ambiguous Lesions**: Lesions that visually share features of melanoma (MEL) and benign keratosis (BKL) often yield split confidence.
- **False Positives for Melanoma**: Due to high penalty for missing a melanoma (high recall priority), the model is conservative, sometimes classifying atypical nevi as MEL.
- **Atypical Presentations**: Rare variations of basal cell carcinoma (BCC) or lesions obscured by hair or poor lighting may be misclassified.
