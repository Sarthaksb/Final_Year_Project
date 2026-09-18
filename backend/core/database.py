"""
backend/core/database.py
-------------------------
Motor async MongoDB client + Beanie ODM initialisation.
Called once on FastAPI startup via the lifespan context manager in main.py.
"""

import motor.motor_asyncio

from core.config import settings

# Single shared Motor client for the entire application lifetime
_mongo_client: motor.motor_asyncio.AsyncIOMotorClient | None = None


def get_motor_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    """Return the module-level Motor client (created on first call)."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongo_url)
    return _mongo_client


async def init_db() -> None:
    """
    Initialise Beanie with all Document models.
    Must be awaited once before any DB operations.
    """
    from beanie import init_beanie
    from models.user import User
    from models.case import Case

    client = get_motor_client()
    await init_beanie(
        database=client[settings.mongo_db_name],
        document_models=[User, Case],
    )


async def close_db() -> None:
    """Close the Motor connection on shutdown."""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
