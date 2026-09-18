"""
backend/api/routes/diagnosis.py
--------------------------------
Diagnosis pipeline endpoint:
  POST /api/diagnosis/analyze
    - Accepts: multipart image file + JSON symptom form
    - Validates: file size (≤ MAX_UPLOAD_MB) and magic bytes (JPEG/PNG/WebP)
    - Runs: ML predict → triage scoring → agent orchestrator → RAG
    - Saves: Case document to MongoDB
    - Returns: full DiagnosisOut

If MODEL_CHECKPOINT_PATH is not set or file not found, returns a MOCK
prediction so the UI can be tested before Colab training is done.
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.dependencies import get_current_user
from core.config import settings
from crud.case import create_case
from crud.diagnosis import run_rag
from models.diagnosis import DiagnosisResult
from models.user import User
from schemas.case import DiagnosisOut, SymptomForm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])

# ── Upload directory setup ────────────────────────────────────────────────────
_UPLOAD_DIR = Path(settings.upload_dir)
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ── Project root on sys.path so ml/triage/agent imports work ──────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Allowed image magic bytes ─────────────────────────────────────────────────
# (first bytes of file, not just extension)
_MAGIC = {
    b"\xff\xd8\xff": ".jpg",          # JPEG
    b"\x89PNG\r\n\x1a\n": ".png",    # PNG
    b"RIFF": ".webp",                 # WebP (bytes 0-3; bytes 8-11 = WEBP)
}
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
}


def _validate_image_magic(content: bytes) -> str:
    """
    Check file magic bytes to verify the upload is a real image.
    Returns the safe extension string ('.jpg', '.png', '.webp').
    Raises HTTPException 415 if the file is not a recognised image format.
    """
    if content[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Uploaded file is not a valid JPEG, PNG, or WebP image.",
    )


# ── Mock prediction (used when no checkpoint exists) ─────────────────────────

_MOCK_RESULT = {
    "predicted_class":  "NV",
    "predicted_label":  1,
    "confidence":       0.82,
    "description":      "Melanocytic Nevus",
    "is_high_risk":     False,
    "all_probabilities": {
        "MEL": 0.05, "NV": 0.82, "BCC": 0.03,
        "AK":  0.02, "BKL": 0.04, "DF": 0.01,
        "VASC": 0.02, "SCC": 0.01,
    },
    "gradcam_path": None,
}


def _run_ml_predict(image_path: Path) -> dict:
    """
    Attempt to run the real EfficientNet-B0 inference.
    Falls back to mock result if checkpoint is missing.
    """
    ckpt = settings.model_checkpoint_path
    if not ckpt or not Path(ckpt).exists():
        logger.debug("No checkpoint found — using mock prediction")
        return _MOCK_RESULT.copy()

    try:
        from ml.classifier.predict import load_model, predict
        model, device = load_model(ckpt)
        return predict(str(image_path), model, device, save_gradcam=False)
    except Exception as exc:
        logger.warning("ML predict error (%s) — falling back to mock", exc)
        return _MOCK_RESULT.copy()


def _run_triage(predicted_class: str, confidence: float, symptoms: dict) -> dict:
    """Run the rule-based triage scorer from triage/scoring.py."""
    try:
        from triage.scoring import compute_urgency
        result = compute_urgency(
            confidence=confidence,
            predicted_class=predicted_class,
            symptoms=symptoms,
        )
        return {
            "urgency":         result.urgency,
            "urgency_reasons": result.reasons,
            "urgency_score":   result.score,
        }
    except Exception as exc:
        logger.warning("Triage error (%s) — using LOW fallback", exc)
        return {"urgency": "LOW", "urgency_reasons": ["Triage unavailable"], "urgency_score": 1}


def _run_agent(predicted_class: str, confidence: float, symptoms: dict) -> dict:
    """
    Run the LangGraph orchestrator if GEMINI_API_KEY is available.
    Returns agent result dict, or a graceful fallback if API key is missing.
    """
    if not settings.gemini_api_key:
        logger.debug("GEMINI_API_KEY not set — skipping agent")
        return {
            "status": "NORMAL",
            "explanation": (
                "AI explanation unavailable — set GEMINI_API_KEY in .env "
                "to enable Gemini-powered explanations."
            ),
        }
    try:
        os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)
        from agent.graph import orchestrator
        state = orchestrator.invoke({
            "predicted_class": predicted_class,
            "confidence":      confidence,
            "symptoms":        symptoms,
        })
        return state.get("result", {})
    except Exception as exc:
        logger.error("Agent error: %s", exc)
        return {"status": "ERROR", "explanation": f"Agent error: {str(exc)[:200]}"}


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=DiagnosisOut,
    status_code=status.HTTP_200_OK,
    summary="Full AI Diagnosis Pipeline",
    response_description="Complete diagnosis result with urgency, agent explanation, and RAG source",
)
async def analyze(
    image: UploadFile = File(..., description="Skin lesion image (JPEG/PNG/WebP, max 10 MB)"),
    symptoms: str = Form(
        default="{}",
        description=(
            "JSON string of boolean symptom flags: "
            "{rapid_growth, bleeding, irregular_border, itching, pain}"
        ),
    ),
    current_user: User = Depends(get_current_user),
):
    """
    Run the full DermaAI diagnostic pipeline:

    1. **Validate** — check file size and magic bytes (not just extension)
    2. **Save** — store the image to disk with a UUID filename
    3. **ML inference** — EfficientNet-B0 classification (mock if no checkpoint)
    4. **Triage scoring** — rule-based HIGH/MEDIUM/LOW urgency
    5. **Agent orchestration** — LangGraph + Gemini explanation (if API key set)
    6. **RAG retrieval** — grounded explanation from medical knowledge base
    7. **Persist** — save full Case document to MongoDB
    8. **Return** — complete DiagnosisOut response
    """
    # ── 1. Parse symptoms ─────────────────────────────────────────────────────
    try:
        symptoms_dict: dict = json.loads(symptoms)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="symptoms must be a valid JSON string, e.g. {\"bleeding\": true}",
        )

    # ── 2. Read file + validate size ──────────────────────────────────────────
    content = await image.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds maximum allowed size of {settings.max_upload_mb} MB.",
        )

    # ── 3. Validate by magic bytes (not just extension) ───────────────────────
    safe_ext = _validate_image_magic(content)
    unique_name = f"{uuid.uuid4().hex}{safe_ext}"
    save_path = _UPLOAD_DIR / unique_name

    try:
        save_path.write_bytes(content)
        logger.info(
            "Image saved: %s (%.1f KB) for user %s",
            unique_name, len(content) / 1024, current_user.id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save image: {exc}",
        )

    # ── 4. ML prediction ──────────────────────────────────────────────────────
    ml_result     = _run_ml_predict(save_path)
    predicted_class: str          = ml_result["predicted_class"]
    confidence:      float        = ml_result["confidence"]
    description:     str          = ml_result["description"]
    is_high_risk:    bool         = ml_result["is_high_risk"]
    all_probs:       dict         = ml_result["all_probabilities"]
    gradcam_path:    Optional[str] = ml_result.get("gradcam_path")

    # ── 5. Triage scoring ─────────────────────────────────────────────────────
    triage = _run_triage(predicted_class, confidence, symptoms_dict)

    # ── 6. Agent orchestrator ─────────────────────────────────────────────────
    agent_result  = _run_agent(predicted_class, confidence, symptoms_dict)
    agent_status: Optional[str] = agent_result.get("status")

    # ── 7. RAG explanation ────────────────────────────────────────────────────
    rag_explanation, rag_source = run_rag(predicted_class)

    # ── 8. Build embedded diagnosis result ────────────────────────────────────
    diagnosis = DiagnosisResult(
        predicted_class  = predicted_class,
        description      = description,
        confidence       = confidence,
        is_high_risk     = is_high_risk,
        all_probabilities= all_probs,
        urgency          = triage["urgency"],
        urgency_reasons  = triage["urgency_reasons"],
        urgency_score    = triage["urgency_score"],
        agent_status     = agent_status,
        agent_result     = agent_result,
        rag_explanation  = rag_explanation,
        rag_source       = rag_source,
        gradcam_path     = gradcam_path,
    )

    # ── 9. Persist to MongoDB ─────────────────────────────────────────────────
    case = await create_case(
        user_id        = str(current_user.id),
        image_filename = unique_name,
        image_path     = str(save_path),
        symptoms       = symptoms_dict,
        result         = diagnosis,
    )

    logger.info(
        "Case created: %s | class=%s | urgency=%s | user=%s",
        case.id, predicted_class, triage["urgency"], current_user.id,
    )

    # ── 10. Return response ───────────────────────────────────────────────────
    return DiagnosisOut(
        predicted_class  = predicted_class,
        description      = description,
        confidence       = confidence,
        is_high_risk     = is_high_risk,
        all_probabilities= all_probs,
        urgency          = triage["urgency"],
        urgency_reasons  = triage["urgency_reasons"],
        urgency_score    = triage["urgency_score"],
        agent_status     = agent_status,
        agent_result     = agent_result,
        rag_explanation  = rag_explanation,
        rag_source       = rag_source,
        gradcam_path     = gradcam_path,
    )
