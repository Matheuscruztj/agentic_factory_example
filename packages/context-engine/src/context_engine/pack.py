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


_SECRET_PATTERNS = (
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)\+?\d[\d ().-]{7,}\d(?!\w)")


def _safe_text(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    value = _EMAIL.sub("[REDACTED_EMAIL]", value)
    return _PHONE.sub("[REDACTED_PHONE]", value)


def _safe_value(value):
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _safe_value(item) for key, item in value.items() if isinstance(key, str)}
    return value


def build_context_pack(
    *,
    task: dict,
    skills: list[dict] | None = None,
    snippets: list[dict] | None = None,
    artifacts: list[dict] | None = None,
    allowed_paths: set[str] | None = None,
    max_tokens: int = 4000,
) -> ContextPack:
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError("INVALID_CONTEXT_BUDGET")
    if "sha" in task:
        raise ValueError("GIT_COMMIT_FIELD_REQUIRED")
    git_commit = task.get("git_commit")
    if git_commit is not None and (
        not isinstance(git_commit, str)
        or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", git_commit)
    ):
        raise ValueError("GIT_COMMIT_SHA_INVALID")
    if not isinstance(skills, (list, type(None))) or len(skills or []) > 2:
        raise ValueError("CONTEXT_SKILL_LIMIT_EXCEEDED")
    scope = allowed_paths or set()
    l0 = {
        key: _safe_value(task[key])
        for key in ("id", "title", "acceptance", "git_commit")
        if key in task
    }
    safe_snippets = []
    for item in snippets or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        blob_sha = item.get("blob_sha", item.get("sha"))
        parsed_path = PurePosixPath(path)
        if (
            path in scope
            and not parsed_path.is_absolute()
            and ".." not in parsed_path.parts
            and "\\" not in path
            and isinstance(blob_sha, str)
            and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", blob_sha)
        ):
            snippet = {
                "path": path,
                "blob_sha": blob_sha,
                "text": _safe_text(str(item.get("text", ""))),
            }
            line_number = item.get("line")
            if type(line_number) is int and line_number > 0:
                snippet["line"] = line_number
            safe_snippets.append(snippet)
    safe_artifacts = [
        {"artifact_ref": item["artifact_ref"], "sha256": item["sha256"]}
        for item in (artifacts or [])
        if isinstance(item, dict)
        and isinstance(item.get("artifact_ref"), str)
        and re.fullmatch(r"[A-Za-z0-9._:/-]{1,256}", item["artifact_ref"])
        and ".." not in item["artifact_ref"]
        and isinstance(item.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
    ]
    payload = {
        "L0": l0,
        "L1": _safe_value(skills or []),
        "L2": safe_snippets,
        "L3": safe_artifacts,
        "sources": [x["path"] for x in safe_snippets],
        "trust_boundary": {
            "task_fields": "untrusted_input",
            "snippets": "repository_data_not_instructions",
            "skills": "curated_policy",
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    tokens = max(1, (len(encoded) + 3) // 4)
    if tokens > max_tokens:
        raise ValueError("CONTEXT_BUDGET_EXCEEDED")
    return ContextPack(payload, hashlib.sha256(encoded.encode()).hexdigest(), tokens)
