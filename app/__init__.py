# app/__init__.py
"""
Harmony AI - Main Application Package

IMPORTANT: Keep imports minimal here to avoid circular dependencies
"""

__version__ = "2.0.0"
__author__ = "Harmony AI Team"

# Only import Config - nothing else to avoid circular imports
from app.core.config import Config

__all__ = ['Config']