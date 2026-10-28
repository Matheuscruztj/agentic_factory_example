"""Redaction for structured application logs; unknown fields are never guessed safe."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_SECRET_KEY = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|api[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_KEY_VALUE = re.compile(
    r"(?i)\b(password|passwd|token|secret|api[_-]?key)\s*([=:])\s*([^\s,;]+)"
)
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")


def redact_text(value: str) -> str:
    """Remove common credential formats while retaining surrounding log context."""
    result = _BEARER.sub("Bearer [REDACTED]", value)
    result = _JWT.sub("[REDACTED_JWT]", result)
    return _KEY_VALUE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", result)


def redact_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Mask sensitive keys recursively and scrub strings before structured emission."""
    output: dict[str, Any] = {}
    for key, value in fields.items():
        if _SECRET_KEY.search(str(key)):
            output[str(key)] = "[REDACTED]"
        elif isinstance(value, Mapping):
            output[str(key)] = redact_fields(value)
        elif isinstance(value, list):
            output[str(key)] = [
                redact_fields(item) if isinstance(item, Mapping)
                else redact_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            output[str(key)] = redact_text(value)
        else:
            output[str(key)] = value
    return output
