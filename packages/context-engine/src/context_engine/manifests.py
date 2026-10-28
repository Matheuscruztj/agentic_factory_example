"""Load and validate repository-owned persona manifest files."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PersonaManifest:
    id: str
    goal: str
    scope: tuple[str, ...]
    tools: tuple[str, ...]
    forbidden: tuple[str, ...]
    escalation: tuple[str, ...]
    rubric_id: str
    max_tool_calls: int
    max_context_tokens: int


def load_manifest(path: str | Path) -> PersonaManifest:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "id",
        "goal",
        "scope",
        "tools",
        "forbidden",
        "escalation",
        "rubric_id",
        "max_tool_calls",
        "max_context_tokens",
    }
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("INVALID_MANIFEST_FIELDS")
    if not all(
        isinstance(data[key], list) and all(isinstance(x, str) and x.strip() for x in data[key])
        for key in ("scope", "tools", "forbidden", "escalation")
    ):
        raise ValueError("INVALID_MANIFEST_LIST")
    if any(
        not isinstance(data[key], str) or not data[key].strip()
        for key in ("id", "goal", "rubric_id")
    ) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", data["id"]):
        raise ValueError("INVALID_MANIFEST_IDENTITY")
    if (
        type(data["max_tool_calls"]) is not int
        or data["max_tool_calls"] < 0
        or type(data["max_context_tokens"]) is not int
        or data["max_context_tokens"] < 1
    ):
        raise ValueError("INVALID_MANIFEST_LIMIT")
    return PersonaManifest(
        data["id"],
        data["goal"],
        tuple(data["scope"]),
        tuple(data["tools"]),
        tuple(data["forbidden"]),
        tuple(data["escalation"]),
        data["rubric_id"],
        data["max_tool_calls"],
        data["max_context_tokens"],
    )
