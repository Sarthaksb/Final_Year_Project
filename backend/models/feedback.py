"""
backend/models/feedback.py
--------------------------
Beanie Document for the 'labeled_feedback' MongoDB collection.
Stores doctor overrides of AI predictions for future model finetuning.
"""

from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class LabeledFeedback(Document):
    case_id: str                         # String representation of Case PydanticObjectId
    doctor_id: str                       # String representation of User (Doctor) PydanticObjectId
    ai_label: str                        # The model's predicted_class
    doctor_label: str                    # The doctor's selected class
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "labeled_feedback"
        use_revision = False
