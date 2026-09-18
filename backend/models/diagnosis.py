"""
backend/models/diagnosis.py
-----------------------------
Embedded Pydantic model for the diagnosis result stored inside a Case document.
Not a Beanie Document itself — embedded as a sub-document.
"""

from typing import Any, Optional

from pydantic import BaseModel


class DiagnosisResult(BaseModel):
    """
    Embedded in Case.result — stores the full pipeline output.

    Fields
    ------
    predicted_class  : ISIC class code e.g. "MEL"
    description      : Human-readable class name e.g. "Melanoma"
    confidence       : Softmax probability 0-1
    is_high_risk     : True if MEL / BCC / SCC
    all_probabilities: Dict of all 8 class probabilities
    urgency          : HIGH | MEDIUM | LOW (from triage/scoring.py)
    urgency_reasons  : List of rule strings that fired
    urgency_score    : Numeric urgency: HIGH=10, MEDIUM=5, LOW=1
    agent_status     : URGENT | NORMAL | NEEDS_MORE_INFO
    agent_result     : Full agent output dict (branch-specific)
    rag_explanation  : Text explanation from RAG pipeline (None until Phase 5)
    rag_source       : Source document filename from RAG
    gradcam_path     : Server path to Grad-CAM PNG (None if no checkpoint)
    """

    predicted_class: str
    description: str
    confidence: float
    is_high_risk: bool
    all_probabilities: dict[str, float]

    urgency: str                        # HIGH | MEDIUM | LOW
    urgency_reasons: list[str]
    urgency_score: int

    agent_status: Optional[str] = None
    agent_result: Optional[dict[str, Any]] = None

    rag_explanation: Optional[str] = None
    rag_source: Optional[str] = None

    gradcam_path: Optional[str] = None
