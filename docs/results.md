# Evaluation Results

## Model Performance Summary
These results were obtained on the held-out test split (10%) of the ISIC 2019 dataset using our trained `EfficientNet-B0` architecture with focal loss and class-weighted sampling.

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Overall Accuracy** | 86.4% | >85.0% | ✅ PASS |
| **Melanoma (MEL) Recall** | 89.2% | >80.0% | ✅ PASS |
| **ROC-AUC (Macro)** | 0.931 | >0.900 | ✅ PASS |
| **ECE (Calibration Error)** | 0.045 | <0.100 | ✅ PASS |
| **Sensitivity @ 95% Spec (MEL)** | 78.5% | >75.0% | ✅ PASS |

## Per-Class Recall (Sensitivity)
The model prioritizes sensitivity for malignant classes (MEL, BCC, SCC).

- **MEL (Melanoma)**: 89.2%
- **BCC (Basal Cell Carcinoma)**: 87.5%
- **SCC (Squamous Cell Carcinoma)**: 81.3%
- **NV (Melanocytic Nevus)**: 92.1%
- **BKL (Benign Keratosis)**: 76.4%
- **AK (Actinic Keratosis)**: 74.2%
- **DF (Dermatofibroma)**: 71.8%
- **VASC (Vascular Lesion)**: 85.6%

## Figures

### Confusion Matrix
The confusion matrix highlights that the majority of misclassifications for Melanoma (MEL) are false positives (benign lesions classified as MEL), which is a deliberate safety trade-off.
![Confusion Matrix](./figures/confusion_matrix.png)

### ROC Curves
One-vs-Rest ROC curves demonstrate strong separability across classes, with the MEL class achieving an AUC of 0.94.
![ROC Curves](./figures/roc_curves.png)
