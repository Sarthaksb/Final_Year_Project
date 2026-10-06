"""
backend/models/case.py
-----------------------
Beanie Document for the 'cases' MongoDB collection.
Each case = one patient image upload + symptom form + full pipeline result.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field

from models.diagnosis import DiagnosisResult
from models.review import DoctorReview


class Case(Document):
    user_id: str                        # stored as str of User PydanticObjectId
    image_filename: str                 # saved filename on server
    image_path: str                     # relative path under uploads/
    lesion_id: Optional[str] = None     # groups cases of the same physical lesion

    # Symptom questionnaire — all default False
    symptom_rapid_growth: bool = False
    symptom_bleeding: bool = False
    symptom_irregular_border: bool = False
    symptom_itching: bool = False
    symptom_pain: bool = False

    result: Optional[DiagnosisResult] = None
    doctor_review: Optional[DoctorReview] = None   # set when a doctor reviews this case
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "cases"
        use_revision = False
