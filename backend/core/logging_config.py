"""
backend/core/logging_config.py
--------------------------------
Structured logging setup for the DermaAI backend.

Call configure_logging() once at startup (in main.py lifespan).
All modules should use:  logger = logging.getLogger(__name__)

Format: ISO-8601 timestamp | level | logger name | message
In production the level can be raised to WARNING via LOG_LEVEL env var.
"""

import logging
import sys
from core.config import settings


def configure_logging() -> None:
    """Configure root logger with consistent format and correct level."""

    level_name = "DEBUG" if settings.environment == "development" else "INFO"
    level = getattr(logging, level_name, logging.INFO)

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called more than once
    if not root.handlers:
        root.addHandler(handler)

    # Quieten noisy third-party loggers
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("beanie").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured | level=%s | env=%s",
        level_name,
        settings.environment,
    )
