"""Progressive, deterministic context packs with explicit sources and budgets."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True, slots=True)
class ContextPack:
    content: dict
    sha256: str
    estimated_tokens: int


def _safe_text(value: str) -> str:
    return re.sub(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+", "[REDACTED]", value)


def build_context_pack(
    *,
    task: dict,
    skills: list[dict] | None = None,
    snippets: list[dict] | None = None,
    artifacts: list[dict] | None = None,
    allowed_paths: set[str] | None = None,
    max_tokens: int = 4000,
) -> ContextPack:
    scope = allowed_paths or set()
    l0 = {key: task[key] for key in ("id", "title", "acceptance", "sha") if key in task}
    safe_snippets = []
    for item in snippets or []:
        path = str(item.get("path", ""))
        parsed_path = PurePosixPath(path)
        if path in scope and not parsed_path.is_absolute() and ".." not in parsed_path.parts:
            safe_snippets.append(
                {
                    "path": path,
                    "sha": item.get("sha"),
                    "text": _safe_text(str(item.get("text", ""))),
                }
            )
    safe_artifacts = [
        {"artifact_ref": item["artifact_ref"], "sha256": item["sha256"]}
        for item in (artifacts or [])
        if "artifact_ref" in item and "sha256" in item
    ]
    payload = {
        "L0": l0,
        "L1": skills or [],
        "L2": safe_snippets,
        "L3": safe_artifacts,
        "sources": [x["path"] for x in safe_snippets],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    tokens = max(1, (len(encoded) + 3) // 4)
    if tokens > max_tokens:
        raise ValueError("CONTEXT_BUDGET_EXCEEDED")
    return ContextPack(payload, hashlib.sha256(encoded.encode()).hexdigest(), tokens)
