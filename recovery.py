from __future__ import annotations

from enum import Enum


class FailureKind(str, Enum):
    TRANSIENT = "transient"
    VALIDATION_ERROR = "validation_error"
    UPSTREAM_FAILURE = "upstream_failure"


TRANSIENT_MARKERS = (
    "503",
    "502",
    "504",
    "timeout",
    "timed out",
    "connection",
    "bad gateway",
    "gateway timeout",
    "connectionerror",
    "httpstatuserror",
    "service unavailable",
)

VALIDATION_MARKERS = (
    "malformed",
    "validationerror",
    "validation error",
    "json decode",
    "invalid json",
    "pydantic",
)


def classify_failure(error: str) -> FailureKind:
    """Classify a node failure so recovery only replans real upstream failures."""

    text = (error or "").lower()
    if any(marker in text for marker in TRANSIENT_MARKERS):
        return FailureKind.TRANSIENT
    if any(marker in text for marker in VALIDATION_MARKERS):
        return FailureKind.VALIDATION_ERROR
    return FailureKind.UPSTREAM_FAILURE
