"""
backend/schemas/user.py
------------------------
Pydantic request/response schemas for auth endpoints.
Separate from Beanie Document models — these are API contracts only.
"""

from pydantic import BaseModel, EmailStr, field_validator


class UserRegister(BaseModel):
    email:     EmailStr
    password:  str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce minimum password requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if v.isdigit():
            raise ValueError("Password must contain at least one letter.")
        if v.isalpha():
            raise ValueError("Password must contain at least one digit.")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name cannot be empty.")
        return v


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class UserOut(BaseModel):
    id:        str
    email:     str
    full_name: str
    role:      str

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut
