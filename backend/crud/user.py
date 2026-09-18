"""
backend/crud/user.py
---------------------
CRUD operations for the User collection via Beanie.
"""

from typing import Optional

from models.user import User
from core.security import hash_password


async def create_user(email: str, password: str, full_name: str, role: str = "patient") -> User:
    """Create and insert a new User document. Raises ValueError if email exists."""
    existing = await User.find_one(User.email == email)
    if existing:
        raise ValueError(f"User with email '{email}' already exists.")
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
    )
    await user.insert()
    return user


async def get_user_by_email(email: str) -> Optional[User]:
    """Return User or None if not found."""
    return await User.find_one(User.email == email)


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Return User by string ID or None."""
    from beanie import PydanticObjectId
    try:
        oid = PydanticObjectId(user_id)
    except Exception:
        return None
    return await User.get(oid)
