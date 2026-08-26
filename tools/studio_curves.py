"""Frozen MaloSound studio-curve pipeline contract.

This module names the canonical stage order used by studio control surfaces.
Do not reorder the stages without an explicit contract migration.
"""

from __future__ import annotations

from typing import Iterable


STUDIO_CURVE_PIPELINE: tuple[str, str, str, str] = (
    "Calibrate",
    "1-Euro Filter",
    "Perception Curve",
    "Dispatch",
)


def assert_studio_curve_pipeline(stages: Iterable[str]) -> None:
    """Raise when a candidate stage list violates the frozen contract."""
    candidate = tuple(stages)
    if candidate != STUDIO_CURVE_PIPELINE:
        expected = " -> ".join(STUDIO_CURVE_PIPELINE)
        actual = " -> ".join(candidate)
        raise ValueError(f"studio curve pipeline changed: expected {expected}; got {actual}")
