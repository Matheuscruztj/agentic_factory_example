"""Store full tool output locally and expose only compact paginated summaries."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

_SUMMARY_REDACTIONS = (
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\w)\+?\d[\d ().-]{7,}\d(?!\w)"),
)


def _safe_summary(value: str) -> str:
    for pattern in _SUMMARY_REDACTIONS:
        value = pattern.sub("[REDACTED]", value)
    return value[:300]


def compact_output(
    root: str | Path, output: str, *, exit_code: int, ttl_seconds: int = 86400
) -> dict:
    if type(ttl_seconds) is not int or ttl_seconds < 1:
        raise ValueError("INVALID_TTL")
    if type(exit_code) is not int or exit_code not in {0, 1, 2}:
        raise ValueError("INVALID_EXIT_CODE")
    base = Path(root).resolve()
    artifacts = base / "tool-outputs"
    artifacts.mkdir(parents=True, exist_ok=True)
    raw = output.encode()
    digest = hashlib.sha256(raw).hexdigest()
    expires_at = int(time.time()) + ttl_seconds
    ref = f"tool-outputs/{digest}.log"
    artifact_path = base / ref
    target = artifact_path.resolve()
    metadata_path = artifacts / f"{digest}.meta"
    if (
        not target.is_relative_to(artifacts.resolve())
        or artifact_path.is_symlink()
        or metadata_path.is_symlink()
        or not metadata_path.resolve().is_relative_to(artifacts.resolve())
    ):
        raise ValueError("ARTIFACT_PATH_NOT_ALLOWED")
    target.write_bytes(raw)
    metadata_path.write_text(str(expires_at), encoding="ascii")
    lines = output.splitlines()
    important = [
        _safe_summary(line)
        for line in lines
        if re.search(r"(?i)error|failed|exception|warning", line)
    ][:10]
    return {
        "status": "pass" if exit_code == 0 else "fail" if exit_code == 1 else "infra",
        "exit_code": exit_code,
        "metrics": {"line_count": len(lines), "byte_count": len(raw)},
        "artifact_ref": ref,
        "sha256": digest,
        "expires_at": expires_at,
        "summary": important,
    }


def read_artifact(
    root: str | Path, artifact_ref: str, *, offset: int = 0, limit: int = 100
) -> dict:
    if not re.fullmatch(r"tool-outputs/[0-9a-f]{64}\.log", artifact_ref):
        raise ValueError("INVALID_ARTIFACT_REF")
    if (
        type(offset) is not int
        or type(limit) is not int
        or offset < 0
        or not 1 <= limit <= 500
    ):
        raise ValueError("INVALID_PAGE")
    base = Path(root).resolve()
    artifact_path = base / artifact_ref
    target = artifact_path.resolve()
    if (
        artifact_path.is_symlink()
        or not target.is_relative_to((base / "tool-outputs").resolve())
        or not target.is_file()
    ):
        raise FileNotFoundError("ARTIFACT_NOT_FOUND")
    metadata = target.with_suffix(".meta")
    artifacts = (base / "tool-outputs").resolve()
    if metadata.is_symlink() or not metadata.resolve().is_relative_to(artifacts):
        raise FileNotFoundError("ARTIFACT_METADATA_MISSING")
    try:
        expires_at = int(metadata.read_text(encoding="ascii"))
    except (OSError, ValueError):
        raise FileNotFoundError("ARTIFACT_METADATA_MISSING") from None
    if expires_at <= int(time.time()):
        raise FileNotFoundError("ARTIFACT_EXPIRED")
    raw = target.read_bytes()
    if hashlib.sha256(raw).hexdigest() != target.stem:
        raise ValueError("ARTIFACT_HASH_MISMATCH")
    lines = raw.decode(errors="replace").splitlines()
    audit_path = artifacts / "access.jsonl"
    if audit_path.is_symlink() or not audit_path.resolve().is_relative_to(artifacts):
        raise ValueError("AUDIT_PATH_NOT_ALLOWED")
    record = json.dumps(
        {"at": int(time.time()), "artifact_ref": artifact_ref, "offset": offset, "limit": limit},
        separators=(",", ":"),
    ) + "\n"
    fd = os.open(audit_path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, record.encode())
    finally:
        os.close(fd)
    return {
        "lines": lines[offset : offset + limit],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "offset": offset,
        "next_offset": min(offset + limit, len(lines)) if offset + limit < len(lines) else None,
    }
