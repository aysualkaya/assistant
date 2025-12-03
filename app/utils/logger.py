# app/utils/logger.py - IMPROVED VERSION
"""
Logging Utilities with Config Support
"""

import logging
import sys
from pathlib import Path
from app.core.config import Config


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Set level from config
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler (always)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File Handler (optional, for debugging)
    if Config.LOG_LEVEL == "DEBUG":
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(
            log_dir / "harmony_ai.log",
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Don't propagate to root logger
    logger.propagate = False
    
    return logger


def set_log_level(level: str):
    """
    Dynamically change log level for all loggers
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.root.setLevel(log_level)
    
    for handler in logging.root.handlers:
        handler.setLevel(log_level)