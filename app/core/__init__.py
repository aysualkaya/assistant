# app/core/__init__.py
"""
Core Package - Configuration, Intent Classification, Schema Building

Keep imports lazy to avoid circular dependencies
"""

# Only essential imports
from app.core.config import Config

__all__ = ['Config']

# Lazy imports - only import when actually needed
def get_intent_classifier():
    """Lazy import to avoid circular dependency"""
    from app.core.intent_classifier import IntentClassifier
    return IntentClassifier

def get_schema_builder():
    """Lazy import to avoid circular dependency"""
    from app.core.schema_builder import DynamicSchemaBuilder
    return DynamicSchemaBuilder