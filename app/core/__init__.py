# app/core/__init__.py
"""
Core Package
============

Contains essential components such as:
- Config
- Lazy-loaded IntentClassifier
- Lazy-loaded DynamicSchemaBuilder

Design Notes:
-------------
We keep imports minimal here to prevent circular dependencies:
SQLGenerator → IntentClassifier
IntentClassifier → Utils/Logger
SchemaBuilder → Used by PromptManager (optional)

Lazy import ensures modules are loaded only when required.
"""

# Direct export — no circular dependency risk
from app.core.config import Config

__all__ = [
    "Config",
    "get_intent_classifier",
    "get_schema_builder",
]


# -----------------------
# Lazy Import Providers
# -----------------------
def get_intent_classifier():
    """Return IntentClassifier class lazily (avoids circular imports)."""
    from app.core.intent_classifier import IntentClassifier
    return IntentClassifier


def get_schema_builder():
    """Return DynamicSchemaBuilder class lazily (avoids circular imports)."""
    from app.core.schema_builder import DynamicSchemaBuilder
    return DynamicSchemaBuilder
