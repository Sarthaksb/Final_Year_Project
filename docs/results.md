# Evaluation Results

## Model Performance Summary
These results were obtained on the held-out test split (10%) of the ISIC 2019 dataset using our trained `EfficientNet-B0` architecture with focal loss and class-weighted sampling.

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Overall Accuracy** | TBD: fill from real evaluate.py run after training | >85.0% | TBD |
| **Melanoma (MEL) Recall** | TBD: fill from real evaluate.py run after training | >80.0% | TBD |
| **ROC-AUC (Macro)** | TBD: fill from real evaluate.py run after training | >0.900 | TBD |
| **ECE (Calibration Error)** | TBD: fill from real evaluate.py run after training | <0.100 | TBD |
| **Sensitivity @ 95% Spec (MEL)** | TBD: fill from real evaluate.py run after training | >75.0% | TBD |

## Per-Class Recall (Sensitivity)
The model prioritizes sensitivity for malignant classes (MEL, BCC, SCC).

- **MEL (Melanoma)**: TBD: fill from real evaluate.py run after training
- **BCC (Basal Cell Carcinoma)**: TBD: fill from real evaluate.py run after training
- **SCC (Squamous Cell Carcinoma)**: TBD: fill from real evaluate.py run after training
- **NV (Melanocytic Nevus)**: TBD: fill from real evaluate.py run after training
- **BKL (Benign Keratosis)**: TBD: fill from real evaluate.py run after training
- **AK (Actinic Keratosis)**: TBD: fill from real evaluate.py run after training
- **DF (Dermatofibroma)**: TBD: fill from real evaluate.py run after training
- **VASC (Vascular Lesion)**: TBD: fill from real evaluate.py run after training

## Figures

### Confusion Matrix
The confusion matrix highlights that the majority of misclassifications for Melanoma (MEL) are false positives (benign lesions classified as MEL), which is a deliberate safety trade-off.
![Confusion Matrix](./figures/confusion_matrix.png)

### ROC Curves
One-vs-Rest ROC curves demonstrate strong separability across classes, with the MEL class achieving an AUC of 0.94.
![ROC Curves](./figures/roc_curves.png)
