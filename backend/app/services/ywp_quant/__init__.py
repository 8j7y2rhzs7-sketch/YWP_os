"""YWP quantitative decision engine."""

from .engine import ENGINE_VERSION, analyze_document

__all__ = ["analyze_document", "ENGINE_VERSION"]
__version__ = ENGINE_VERSION
