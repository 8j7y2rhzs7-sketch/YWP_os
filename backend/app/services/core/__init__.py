"""Shared pure helpers used by markets mode.

The live sports decision engine is intentionally left on its own code path.
These functions copy its published thresholds so a markets call uses the same
ladder, edge labels, and quarter-Kelly sizing without changing sports output.
"""
