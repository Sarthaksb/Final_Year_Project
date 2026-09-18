"""
backend/schemas/case.py
------------------------
Pydantic request/response schemas for case/diagnosis endpoints.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SymptomForm(BaseModel):
    """Symptom questionnaire submitted alongside the image upload."""
    rapid_growth: bool = False
    bleeding: bool = False
    irregular_border: bool = False
    itching: bool = False
    pain: bool = False


class DiagnosisOut(BaseModel):
    """Full diagnosis result returned to the frontend."""
    predicted_class: str
    description: str
    confidence: float
    is_high_risk: bool
    all_probabilities: dict[str, float]

    urgency: str
    urgency_reasons: list[str]
    urgency_score: int

    agent_status: Optional[str] = None
    agent_result: Optional[dict[str, Any]] = None

    rag_explanation: Optional[str] = None
    rag_source: Optional[str] = None

    gradcam_path: Optional[str] = None


class CaseOut(BaseModel):
    """Single case summary returned by list/detail endpoints."""
    id: str
    image_filename: str
    created_at: datetime
    symptoms: dict[str, bool]
    result: Optional[DiagnosisOut] = None

    model_config = {"from_attributes": True}
