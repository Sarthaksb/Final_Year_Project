"""
backend/models/lesion.py
------------------------
Beanie Document for the 'lesions' MongoDB collection.
Groups multiple Case documents for longitudinal tracking of the same physical lesion.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field


class Lesion(Document):
    patient_id: str                      # String representation of User PydanticObjectId
    body_site: str                       # e.g., "Left arm", "Back"
    label: str                           # e.g., "Mole on left arm"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "lesions"
        use_revision = False
