# app/utils/logger.py
"""
Unified Logging System (2025 Production Version)

Features:
- Safe LOG_LEVEL handling (no attribute errors)
- Console + optional file logging
- Rotating file logs (recommended for production)
- No duplicate handlers
- Does not leak logs to root logger
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.core.config import Config


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""

    logger = logging.getLogger(name)

    # Prevent duplicate handlers in reload cycles
    if logger.handlers:
        return logger

    # ----------------------------------------------------
    # SAFE LEVEL FETCH
    # ----------------------------------------------------
    level_name = getattr(Config, "LOG_LEVEL", "INFO")
    if not isinstance(level_name, str):
        level_name = "INFO"

    log_level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(log_level)

    # ----------------------------------------------------
    # FORMATTER
    # ----------------------------------------------------
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ----------------------------------------------------
    # CONSOLE HANDLER (always on)
    # ----------------------------------------------------
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(log_level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # ----------------------------------------------------
    # FILE HANDLER (recommended for prod, optional)
    # Use rotating logs to prevent giant files.
    # ----------------------------------------------------
    if getattr(Config, "ENABLE_FILE_LOGS", False):
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_handler = RotatingFileHandler(
            log_dir / "harmony_ai.log",
            maxBytes=5 * 1024 * 1024,   # 5 MB per file
            backupCount=3,              # keep last 3 logs
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # ----------------------------------------------------
    # Prevent propagation to root logger
    # ----------------------------------------------------
    logger.propagate = False

    return logger


def set_log_level(level: str):
    """Dynamically change all logger levels at runtime."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.root.setLevel(log_level)

    for handler in logging.root.handlers:
        handler.setLevel(log_level)
