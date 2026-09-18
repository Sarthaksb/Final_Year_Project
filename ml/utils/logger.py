"""
ml/utils/logger.py
Shared logging configuration for all ML modules.
Call `get_logger(__name__)` at the top of any module.
"""

import logging
import sys
from pathlib import Path


def get_logger(name: str, log_file: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """
    Returns a logger with a consistent format.
    If log_file is provided, also writes to that file (append mode).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        # Avoid adding duplicate handlers if called multiple times
        return logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Optional file handler
    if log_file is not None:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    logger.propagate = False
    return logger
