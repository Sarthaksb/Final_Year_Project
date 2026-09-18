"""
backend/models/review.py
-------------------------
Embedded Pydantic model for a doctor's review decision on a Case.
Not a standalone Beanie Document — stored inside Case.doctor_review.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


class DoctorReview(BaseModel):
    """
    Fields
    ------
    doctor_id       : str(User.id) of the reviewing doctor
    doctor_name     : Doctor's full name (denormalised for PDF generation)
    decision        : 'accepted' — agrees with AI prediction
                      'overridden' — replaces AI prediction with own class
    override_class  : ISIC class code chosen by doctor (only when overridden)
    notes           : Free-text clinical notes (optional)
    reviewed_at     : UTC timestamp of the review submission
    """

    doctor_id: str
    doctor_name: str
    decision: Literal["accepted", "overridden"]
    override_class: Optional[str] = None   # set only when decision == "overridden"
    notes: Optional[str] = None
    reviewed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
