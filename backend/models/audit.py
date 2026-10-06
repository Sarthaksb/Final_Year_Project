from datetime import datetime, timezone
from beanie import Document
from pydantic import Field

class AuditLog(Document):
    user_id: str
    user_email: str
    user_role: str
    action: str  # "view", "edit", "review_submitted", etc.
    case_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Settings:
        name = "audit_logs"
