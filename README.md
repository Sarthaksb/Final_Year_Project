# AI-Powered Smart Dermatology and Intelligent Diagnostic System

DermaAI is a clinical decision support system that uses an EfficientNet-B0 classifier, a rule-based triage system, and an LLM-powered orchestration agent to provide preliminary evaluations of skin lesions. It is designed to assist patients in deciding whether to seek immediate dermatological consultation.

**Disclaimer**: This is a decision support tool, not a diagnostic device.

## Overview

The system allows patients to upload a photo of a skin lesion along with a symptom questionnaire. The pipeline processes the image to predict the lesion class (e.g., Melanoma, Basal Cell Carcinoma), calculates an urgency score, and synthesizes a plain-language explanation using RAG over medical guidelines. Doctors can review cases, track lesion progression over time, and provide feedback on AI predictions.

## Architecture

```mermaid
flowchart TD
    subgraph Frontend [React Frontend]
        PatientUI[Patient Upload & Timeline]
        DoctorUI[Doctor Review & Override]
        AdminUI[Admin Analytics]
    end

    subgraph Backend [FastAPI Backend]
        API[FastAPI Endpoints]
        Quality[Image Quality Check (OpenCV)]
        Triage[Rule-Based Triage]
        
        subgraph ML [Machine Learning]
            Classifier[EfficientNet-B0 Model]
            Agent[LangGraph Orchestrator]
            RAG[Retrieval-Augmented Gen]
        end
        
        API --> Quality
        Quality --> Classifier
        Classifier --> Triage
        Triage --> Agent
        Agent <--> RAG
    end

    subgraph Database [MongoDB]
        Users[(Users)]
        Cases[(Cases)]
        Lesions[(Lesions)]
        Audit[(AuditLogs)]
    end

    Frontend <--> API
    API <--> Database
```

## Setup & Installation

The project is fully dockerized for easy deployment.

1. **Clone the repository**
2. **Environment Setup**: Copy `.env.example` to `.env` and fill in your `GEMINI_API_KEY`.
3. **Run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```
4. **Access the Application**:
   - Frontend: `http://localhost:5173`
   - Backend API Docs: `http://localhost:8000/docs`

## Screenshots
*(Placeholders for actual screenshots)*

| Patient Upload | Results Dashboard | Doctor Review |
|----------------|-------------------|---------------|
| ![Upload](docs/figures/screenshot_upload.png) | ![Results](docs/figures/screenshot_results.png) | ![Doctor](docs/figures/screenshot_doctor.png) |

## Evaluation Results

Our EfficientNet-B0 model was trained on the ISIC 2019 dataset, heavily prioritizing recall for malignant classes.

| Metric | Value | Status |
|--------|-------|--------|
| **Accuracy** | 86.4% | ✅ |
| **Melanoma Recall** | 89.2% | ✅ |
| **ROC-AUC (Macro)** | 0.931 | ✅ |

*For the complete report, including the confusion matrix and calibration details, see [Evaluation Results](docs/results.md).*

## Limitations & Known Issues

- **Hardware Gap**: The AI was trained primarily on high-quality dermoscopic images, which causes a domain shift when evaluating standard smartphone photos.
- **Skin Tone Bias**: The model lacks extensive validation on darker skin tones (Fitzpatrick IV-VI).
- **Not a Diagnostic Tool**: It errs on the side of caution (high false-positive rate for malignancies) to ensure patients do not ignore potentially life-threatening lesions.

For deeper insights, please read the [Model Card](docs/MODEL_CARD.md).
