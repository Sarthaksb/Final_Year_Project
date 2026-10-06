"""
backend/models/user.py
-----------------------
Beanie Document for the 'users' MongoDB collection.
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from beanie import Document
from pydantic import EmailStr, Field


class User(Document):
    email: EmailStr
    hashed_password: str
    full_name: str
    role: Literal["patient", "doctor", "admin"] = "patient"
    consent_given: bool = False
    consent_timestamp: Optional[datetime] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "users"          # MongoDB collection name
        use_revision = False
