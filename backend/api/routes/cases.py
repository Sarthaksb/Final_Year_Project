"""
backend/api/routes/cases.py
----------------------------
Patient case history routes:

  GET    /api/cases           — paginated list of current user's cases (newest first)
  GET    /api/cases/{case_id} — single case detail (403 if belongs to another user)
  DELETE /api/cases/{case_id} — delete own case + image (GDPR / data control)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import get_current_user
from core.config import settings
from crud.case import count_cases_by_user, delete_case, get_case_by_id, get_cases_by_user
from models.user import User
from schemas.case import CaseOut, DiagnosisOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["cases"])


# ── Shared helper ─────────────────────────────────────────────────────────────

def _case_to_schema(case) -> CaseOut:
    """Convert a Case Beanie document to a CaseOut response schema."""
    symptoms = {
        "rapid_growth":     case.symptom_rapid_growth,
        "bleeding":         case.symptom_bleeding,
        "irregular_border": case.symptom_irregular_border,
        "itching":          case.symptom_itching,
        "pain":             case.symptom_pain,
    }
    result_out: Optional[DiagnosisOut] = None
    if case.result:
        r = case.result
        result_out = DiagnosisOut(
            predicted_class  = r.predicted_class,
            description      = r.description,
            confidence       = r.confidence,
            is_high_risk     = r.is_high_risk,
            all_probabilities= r.all_probabilities,
            urgency          = r.urgency,
            urgency_reasons  = r.urgency_reasons,
            urgency_score    = r.urgency_score,
            agent_status     = r.agent_status,
            agent_result     = r.agent_result,
            rag_explanation  = r.rag_explanation,
            rag_source       = r.rag_source,
            gradcam_path     = r.gradcam_path,
        )
    return CaseOut(
        id             = str(case.id),
        image_filename = case.image_filename,
        created_at     = case.created_at,
        symptoms       = symptoms,
        result         = result_out,
    )


# ── GET /api/cases ────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[CaseOut],
    summary="List patient case history",
    response_description="Paginated list of cases, newest first",
)
async def list_cases(
    skip:  int = Query(default=0,  ge=0,  description="Number of records to skip"),
    limit: int = Query(default=50, ge=1, le=200, description="Max records to return (1–200)"),
    current_user: User = Depends(get_current_user),
):
    """
    Return the authenticated patient's cases, newest first.
    Supports pagination via `?skip=0&limit=50`.
    """
    cases = await get_cases_by_user(str(current_user.id), skip=skip, limit=limit)
    total = await count_cases_by_user(str(current_user.id))
    logger.debug("list_cases: user=%s skip=%d limit=%d total=%d", current_user.id, skip, limit, total)
    return [_case_to_schema(c) for c in cases]


# ── GET /api/cases/{case_id} ──────────────────────────────────────────────────

@router.get(
    "/{case_id}",
    response_model=CaseOut,
    summary="Get single case detail",
)
async def get_case(
    case_id:      str,
    current_user: User = Depends(get_current_user),
):
    """
    Return a single case with the full AI diagnosis result.
    Returns **403** if the case belongs to a different user.
    Returns **404** if the case ID is invalid or not found.
    """
    case = await get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.user_id != str(current_user.id) and current_user.role != "doctor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _case_to_schema(case)


# ── DELETE /api/cases/{case_id} ───────────────────────────────────────────────

@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a case (patient data erasure)",
)
async def remove_case(
    case_id:      str,
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete a case and its associated image file.

    - Only the **patient who owns the case** can delete it.
    - Doctors cannot use this endpoint (use the audit trail instead).
    - Returns **204 No Content** on success.
    - Returns **403** if another user tries to delete the case.
    - Returns **404** if the case is not found.
    """
    case = await get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    if case.user_id != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own cases.",
        )

    await delete_case(case_id, upload_dir=settings.upload_dir)
    logger.info("Case %s deleted by user %s", case_id, current_user.id)
    # 204 returns no body
