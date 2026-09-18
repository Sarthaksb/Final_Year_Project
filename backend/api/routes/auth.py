"""
backend/api/routes/auth.py
---------------------------
Authentication routes:
  POST /api/auth/register  — create patient account
  POST /api/auth/login     — return JWT access token
"""

from fastapi import APIRouter, HTTPException, status

from core.security import create_access_token, verify_password
from crud.user import create_user, get_user_by_email
from schemas.user import Token, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister):
    """Register a new patient account and return a JWT token."""
    try:
        user = await create_user(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    token = create_access_token({"sub": str(user.id)})
    return Token(
        access_token=token,
        user=UserOut(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        ),
    )


@router.post("/login", response_model=Token)
async def login(body: UserLogin):
    """Authenticate a user and return a JWT token."""
    user = await get_user_by_email(body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": str(user.id)})
    return Token(
        access_token=token,
        user=UserOut(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
        ),
    )
