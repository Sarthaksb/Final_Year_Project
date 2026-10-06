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
import cv2
import numpy as np
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from api.dependencies import get_current_user
from core.config import settings
from crud.case import create_case
from models.case import Case
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


def _run_ml_predict(image_path: Path, request: Request) -> dict:
    """
    Attempt to run the real EfficientNet-B0 inference using the globally loaded model.
    If the model is unavailable, return MODEL_UNAVAILABLE error instead of a fake prediction.
    """
    model = getattr(request.app.state, "ml_model", None)
    device = getattr(request.app.state, "ml_device", None)

    if model is None or device is None:
        logger.warning("Inference attempted but ML Model is unavailable in app state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MODEL_UNAVAILABLE: The diagnostic model is currently offline."
        )

    try:
        from ml.classifier.predict import predict
        return predict(str(image_path), model, device, save_gradcam=False)
    except Exception as exc:
        logger.error("ML predict error (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during model inference."
        )


def _run_triage(
    predicted_class: str,
    confidence: float,
    symptoms: dict,
    all_probs: dict | None = None,
    is_lesion_changed: bool = False,
) -> dict:
    """Run the rule-based triage scorer from triage/scoring.py."""
    try:
        from triage.scoring import compute_urgency
        result = compute_urgency(
            confidence=confidence,
            predicted_class=predicted_class,
            symptoms=symptoms,
            all_probabilities=all_probs,
            is_lesion_changed=is_lesion_changed,
        )
        return {
            "urgency":         result.urgency,
            "urgency_reasons": result.reasons,
            "urgency_score":   result.score,
        }
    except Exception as exc:
        logger.warning("Triage error (%s) -- using LOW fallback", exc)
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


# ── 1. Image Quality Check ──────────────────────────────────────────────────────

@router.post("/check-quality")
async def check_image_quality(image: UploadFile = File(...)):
    """
    Check uploaded image for blur, brightness, and resolution before analysis.
    Returns warnings or reject flag.
    """
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file.")
        
    height, width, _ = img.shape
    
    # Calculate blur using Laplacian variance
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Calculate mean brightness
    brightness = np.mean(gray)
    
    warnings = []
    reject = False
    
    if height < 200 or width < 200:
        warnings.append("Resolution is very low. Please capture closer or use a higher quality camera.")
        reject = True
        
    if lap_var < 50:
        warnings.append("Image appears significantly blurry. Please retake keeping the camera steady.")
        if lap_var < 20: reject = True
    elif lap_var < 100:
        warnings.append("Image is slightly blurry. Consider retaking for better results.")
        
    if brightness < 40:
        warnings.append("Image is too dark. Please move to a well-lit area or use flash.")
        if brightness < 20: reject = True
    elif brightness > 230:
        warnings.append("Image is overexposed (too bright). Reduce glare or flash.")
        
    return {
        "blur_score": lap_var,
        "brightness": brightness,
        "resolution": f"{width}x{height}",
        "reject": reject,
        "messages": warnings
    }

# ── 2. Full pipeline ──────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=DiagnosisOut,
    status_code=status.HTTP_200_OK,
    summary="Full AI Diagnosis Pipeline",
    response_description="Complete diagnosis result with urgency, agent explanation, and RAG source",
)
async def analyze(
    request: Request,
    image: UploadFile = File(..., description="Skin lesion image (JPEG/PNG/WebP, max 10 MB)"),
    symptoms: str = Form(
        default="{}",
        description=(
            "JSON string of boolean symptom flags: "
            "{rapid_growth, bleeding, irregular_border, itching, pain}"
        ),
    ),
    lesion_id: Optional[str] = Form(None, description="Optional ID of tracked lesion"),
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
    ml_result = _run_ml_predict(save_path, request)

    # ── OOD gate: reject non-skin images before any triage/case creation ──────
    if ml_result.get("ood_rejected"):
        save_path.unlink(missing_ok=True)   # don't keep the rejected image
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "invalid_image",
                "message": (
                    "The uploaded image does not appear to be a skin lesion photo. "
                    "Please upload a clear, close-up photograph of the skin area of concern."
                ),
            },
        )

    predicted_class: str           = ml_result["predicted_class"]
    confidence:      float         = ml_result["confidence"]
    description:     str           = ml_result["description"]
    is_high_risk:    bool          = ml_result["is_high_risk"]
    all_probs:       dict          = ml_result["all_probabilities"]
    gradcam_path:    Optional[str] = ml_result.get("gradcam_path")

    # ── Check for lesion changes ──────────────────────────────────────────────
    is_lesion_changed = False
    if lesion_id:
        prev_case = await Case.find(Case.lesion_id == lesion_id).sort("-created_at").first_or_none()
        if prev_case and prev_case.result:
            p_probs = prev_case.result.all_probabilities
            prev_score = p_probs.get("MEL", 0) + p_probs.get("BCC", 0) + p_probs.get("SCC", 0)
            curr_score = all_probs.get("MEL", 0) + all_probs.get("BCC", 0) + all_probs.get("SCC", 0)
            if curr_score - prev_score >= 0.15:
                is_lesion_changed = True

    # ── 5. Triage scoring (pass all_probs for malignancy score) ──────────────
    triage = _run_triage(predicted_class, confidence, symptoms_dict, all_probs, is_lesion_changed)


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
        lesion_id      = lesion_id,
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
