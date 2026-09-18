"""
backend/core/config.py
-----------------------
Pydantic BaseSettings: loads all config from environment / .env file.
All values have safe development defaults.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongo_url:     str = "mongodb://localhost:27017"
    mongo_db_name: str = "dermatology"

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret:         str = "change_this_to_a_long_random_string_min_32_chars"
    jwt_algorithm:      str = "HS256"
    jwt_expire_minutes: int = 60

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── ML ────────────────────────────────────────────────────────────────────
    # If empty or file not found → backend uses MOCK predictions
    model_checkpoint_path: str = ""

    # ── File uploads ──────────────────────────────────────────────────────────
    upload_dir:    str = "uploads"
    max_upload_mb: int = 10          # server-side size limit for image uploads

    # ── Application ───────────────────────────────────────────────────────────
    environment: str = "development"   # development | production
    app_name:    str = "DermaAI API"
    api_prefix:  str = "/api"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
