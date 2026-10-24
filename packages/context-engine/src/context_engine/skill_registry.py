"""Curated skill registry; callers cannot resolve arbitrary issue paths."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Skill:
    id: str
    version: str
    triggers: tuple[str, ...]
    weight: int
    file: str
    sha256: str


def load_registry(path: str | Path) -> tuple[Skill, ...]:
    registry = Path(path).resolve()
    data = json.loads(registry.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("skills"), list):
        raise ValueError("INVALID_SKILL_REGISTRY")
    result = []
    seen = set()
    for entry in data["skills"]:
        skill_id, filename = entry.get("id"), entry.get("file")
        if (
            not isinstance(skill_id, str)
            or skill_id in seen
            or not re.fullmatch(r"[a-z0-9-]+", skill_id)
        ):
            raise ValueError("INVALID_OR_DUPLICATE_SKILL_ID")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError("INVALID_SKILL_PATH")
        content_path = (registry.parent / filename).resolve()
        if content_path.parent != registry.parent or not content_path.is_file():
            raise ValueError("SKILL_FILE_MISSING")
        content_hash = hashlib.sha256(content_path.read_bytes()).hexdigest()
        result.append(
            Skill(
                skill_id,
                entry["version"],
                tuple(entry["triggers"]),
                int(entry["weight"]),
                filename,
                content_hash,
            )
        )
        seen.add(skill_id)
    return tuple(result)
