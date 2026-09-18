"""
backend/seeds/seed.py
----------------------
Seeds the MongoDB database with initial test data:
  - 1 doctor account
  - 2 patient accounts

Run from the backend/ directory:
    python -m seeds.seed

Idempotent: skips creation if the email already exists.
"""

import asyncio
from pathlib import Path
import sys

# ── make sure project root is on sys.path ─────────────────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))


async def seed():
    from core.database import init_db, close_db
    from crud.user import create_user, get_user_by_email

    await init_db()

    users_to_seed = [
        {
            "email": "doctor@dermaai.com",
            "password": "doctor123",
            "full_name": "Dr. Sarah Johnson",
            "role": "doctor",
        },
        {
            "email": "patient1@example.com",
            "password": "patient123",
            "full_name": "Alice Sharma",
            "role": "patient",
        },
        {
            "email": "patient2@example.com",
            "password": "patient123",
            "full_name": "Bob Patel",
            "role": "patient",
        },
    ]

    for u in users_to_seed:
        existing = await get_user_by_email(u["email"])
        if existing:
            print(f"  SKIP  {u['email']} (already exists, role={existing.role})")
        else:
            created = await create_user(
                email=u["email"],
                password=u["password"],
                full_name=u["full_name"],
                role=u["role"],
            )
            print(f"  CREATED  {u['role']} — {u['email']} (id={created.id})")

    await close_db()
    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
