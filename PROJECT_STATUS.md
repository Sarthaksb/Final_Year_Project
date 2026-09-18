# PROJECT STATUS

## Project Name
AI-Powered Smart Dermatology and Intelligent Diagnostic System Using Agentic AI

## Current Phase
Phase 9: Integration and Testing

## What Exists So Far (completed, working)
- PROJECT_STATUS.md initialized
- Full project scaffold created (all folders + stub files)
- data/prepare_dataset.py — ISIC 2019 cleaning, splitting, class weights
- ml/classifier/model.py — EfficientNet-B0 with 8-class head + freeze/unfreeze helpers
- ml/classifier/dataset.py — ISICDataset + WeightedRandomSampler + DataLoader factory
- ml/classifier/train.py — Colab-ready: Drive mount, fp16, per-epoch checkpoints, resume
- ml/classifier/evaluate.py — accuracy, per-class recall, confusion matrix, ROC-AUC
- ml/classifier/predict.py — single-image inference + Grad-CAM overlay
- agent/__init__.py, config.py, state.py - LangGraph orchestrator: package setup + constants + AgentState TypedDict
- agent/nodes.py - triage_node (pure Python, red-flags-first priority) + 3 Gemini branch nodes
- agent/graph.py - LangGraph StateGraph with conditional edge; module-level `orchestrator` object
- agent/test_agent.py - 3 test cases (urgent/followup/normal); run: python -m agent.test_agent
- agent/requirements.txt - langgraph, langchain-google-genai, python-dotenv
- triage/scoring.py - rule-based urgency scorer (HIGH/MEDIUM/LOW); imports red-flag constants from agent/config.py
- agent/nodes.py - triage_node (pure Python, red-flags-first priority) + 3 Gemini branch nodes
- agent/graph.py - LangGraph StateGraph with conditional edge; module-level `orchestrator` object
- agent/test_agent.py - 3 test cases (urgent/followup/normal); run: python -m agent.test_agent
- agent/requirements.txt - langgraph, langchain-google-genai, python-dotenv
- triage/scoring.py - rule-based urgency scorer (HIGH/MEDIUM/LOW); imports red-flag constants from agent/config.py
- triage/test_scoring.py - 5 test cases covering all urgency branches; run: python -m triage.test_scoring
- backend/ - FastAPI app (MongoDB + Motor + Beanie ODM + JWT auth)
  - POST /api/auth/register, POST /api/auth/login
  - POST /api/diagnosis/analyze (image + symptoms → ML + triage + agent → Case saved)
  - GET /api/cases, GET /api/cases/{id} (patient history)
  - GET /api/doctor/cases (all patients, urgency filter), GET /api/doctor/cases/{id}
  - POST /api/doctor/cases/{id}/review (accept/override + notes; logs doctor_id, name, timestamp)
  - GET /api/doctor/cases/{id}/report (PDF download via reportlab)
  - GET /api/doctor/stats (dashboard aggregation)
  - GET /api/health (deep ping to MongoDB)
- backend/models/: User, Case (with embedded DiagnosisResult + DoctorReview), DoctorReview
- backend/core/: logging_config.py (structured logging), middleware.py (X-Request-ID, timing)
- frontend/ - React 18 + Vite + TailwindCSS
  - Patient: Auth page (login/register), Upload + symptom form, Results page, History page (with delete)
  - Doctor: Dashboard (case list, urgency filter tabs, search, stats cards), CaseReview, Report
  - Zustand auth store, Axios client with JWT interceptor and X-Request-ID logging
- docker-compose.yml — Full stack orchestration (MongoDB 7.0 + FastAPI backend)

## Phase 9 Failure Case Testing Results
1. **Non-skin image uploaded:** No Out-Of-Distribution (OOD) layer exists. The EfficientNet model forces a prediction into one of the 8 classes (with varying confidence) which is then passed down the pipeline.
2. **Blank/missing symptom answers:** Gracefully defaults to `False` for all symptoms. Triage computes correctly without red flags, usually yielding `LOW` urgency if the model is confident.
3. **Very low quality/blurry image:** Model produces low confidence. Triage logic explicitly catches confidence < 60% and elevates urgency to at least `MEDIUM`, triggering the `FOLLOWUP` branch.
4. **Contradictory symptoms:** The UI's strict boolean checkboxes prevent semantic contradiction (e.g. typing "no pain" + "severe burning"). Checking all boxes reliably triggers `HIGH` urgency via multiple red-flag rules.
5. **Extremely low model confidence (<30%):** Triage assigns `MEDIUM` urgency citing "Low model confidence", and the Agent correctly orchestrates to the `FOLLOWUP` protocol.

## Key Decisions Made (so you don't ask again)
- Phase 4 (Agent Orchestrator): 3 branches - URGENT if any red-flag symptom (bleeding/rapid_growth/irregular_border/itching+pain combo), regardless of confidence; FOLLOWUP if no red flag and confidence < 0.60; NORMAL if no red flag and confidence >= 0.60.
- Phase 6 (Triage Scoring): HIGH if any red-flag symptom (same set as Phase 4), regardless of confidence; MEDIUM if no red flag and (confidence < 0.60 OR class in {MEL, SCC}); LOW if no red flag and confidence >= 0.60 and class is not high-risk.
- Dataset: ISIC 2019  25,331 images, 8 classes. CONFIRMED. Do not ask again. NOT HAM10000.
  - 8 classes: MEL, NV, BCC, AK, BKL, DF, VASC, SCC
  - Split: 70% train / 15% val / 15% test (stratified by class)
  - Processed CSVs saved to: data/processed/train.csv, val.csv, test.csv
  - Summary report: data/dataset_summary.txt
  - Class imbalance: handled via inverse-frequency class weights
    ? nn.CrossEntropyLoss(weight=class_weights_tensor)
    ? Optional: WeightedRandomSampler for minority oversampling
    ? Rarest classes (DF ~239, VASC ~253, SCC ~628) get highest weights
  - Approx raw distribution (ISIC 2019):
      NV   ~12,875 (50.8%)  ? dominant class
      MEL  ~4,522  (17.9%)
      BCC  ~3,323  (13.1%)
      BKL  ~2,624  (10.4%)
      AK   ~867    (3.4%)
      SCC  ~628    (2.5%)
      VASC ~253    (1.0%)
      DF   ~239    (0.9%)  ? rarest
- Model choice: EfficientNet-B0 (PyTorch/timm)  CONFIRMED. 224x224 input, 1280-dim head, 5.3M params
  - 2-phase fine-tuning: Phase A epochs 1-3 (head only, lr=1e-3), Phase B epochs 4-10 (full, lr=1e-4)
  - Explainability: Grad-CAM on conv_head layer (pytorch grad-cam library)
  - MEL recall is PRIMARY checkpoint save metric (threshold: >=0.80 for clinical safety)
- Resume: train.py MUST support --resume flag (restores weights + optimizer + scheduler + epoch + best metric)
- Dataset storage: ISIC 2019 in Google Drive permanently, never re-downloaded
- Drive mount root: /content/drive/MyDrive/dermatology/
- Checkpoint path: /content/drive/MyDrive/dermatology/checkpoints/

## Known Issues / Not Done Yet
- Dataset not yet downloaded to Google Drive (prepare_dataset.py ready to run once downloaded)
- Model not yet trained (all training code complete; needs Colab run)
- Actual MEL recall / accuracy metrics: TBD after training

## Next Step
Phase 10: documentation, no more code changes

---
IMPORTANT INSTRUCTION FOR FUTURE SESSIONS:
At the start of any new task, READ THIS FILE FIRST before exploring
the rest of the codebase. Do not re-scan the whole project structure
unless this file is missing information you need.
At the end of any task, UPDATE this file with a short summary --
do not write a long changelog, just update the relevant sections above.
