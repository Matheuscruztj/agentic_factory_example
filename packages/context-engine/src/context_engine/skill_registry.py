"""Curated skill registry; callers cannot resolve arbitrary issue paths."""

from __future__ import annotations

import hashlib
import hmac
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
    if (
        not isinstance(data, dict)
        or type(data.get("version")) is not int
        or data.get("version") != 1
        or not isinstance(data.get("skills"), list)
    ):
        raise ValueError("INVALID_SKILL_REGISTRY")
    result = []
    seen = set()
    for entry in data["skills"]:
        if not isinstance(entry, dict):
            raise ValueError("INVALID_SKILL_ENTRY")
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
        expected_hash = entry.get("sha256")
        if (
            not isinstance(expected_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            or not hmac.compare_digest(content_hash, expected_hash)
        ):
            raise ValueError("SKILL_HASH_MISMATCH")
        version = entry.get("version")
        triggers = entry.get("triggers")
        weight = entry.get("weight")
        if (
            not isinstance(version, str)
            or not version.strip()
            or not isinstance(triggers, list)
            or not triggers
            or not all(isinstance(trigger, str) and trigger.strip() for trigger in triggers)
            or type(weight) is not int
            or weight < 1
        ):
            raise ValueError("INVALID_SKILL_METADATA")
        result.append(
            Skill(
                skill_id,
                version,
                tuple(triggers),
                weight,
                filename,
                content_hash,
            )
        )
        seen.add(skill_id)
    return tuple(result)
