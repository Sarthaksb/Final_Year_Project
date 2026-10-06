"""
backend/schemas/doctor.py
--------------------------
Pydantic request/response schemas for the doctor dashboard endpoints.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel

from schemas.case import DiagnosisOut


# ── Request ───────────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    """Body for POST /api/doctor/cases/{case_id}/review"""
    decision: Literal["accepted", "overridden"]
    override_class: Optional[str] = None   # required when decision == "overridden"
    notes: Optional[str] = None


# ── Response fragments ────────────────────────────────────────────────────────

class ReviewOut(BaseModel):
    doctor_id: str
    doctor_name: str
    decision: str
    override_class: Optional[str] = None
    notes: Optional[str] = None
    reviewed_at: datetime


class DoctorCaseOut(BaseModel):
    """Extended case view returned by doctor endpoints — includes review info."""
    id: str
    user_id: str
    image_filename: str
    created_at: datetime
    symptoms: dict[str, bool]
    result: Optional[DiagnosisOut] = None
    doctor_review: Optional[ReviewOut] = None
    lesion_id: Optional[str] = None

    model_config = {"from_attributes": True}
