"""Store full tool output locally and expose only compact paginated summaries."""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path


def compact_output(
    root: str | Path, output: str, *, exit_code: int, ttl_seconds: int = 86400
) -> dict:
    if ttl_seconds < 1:
        raise ValueError("INVALID_TTL")
    base = Path(root).resolve()
    artifacts = base / "tool-outputs"
    artifacts.mkdir(parents=True, exist_ok=True)
    raw = output.encode()
    digest = hashlib.sha256(raw).hexdigest()
    ref = f"tool-outputs/{digest}.log"
    target = (base / ref).resolve()
    if not target.is_relative_to(artifacts.resolve()):
        raise ValueError("ARTIFACT_PATH_NOT_ALLOWED")
    target.write_bytes(raw)
    (artifacts / f"{digest}.meta").write_text(str(int(time.time()) + ttl_seconds), encoding="ascii")
    lines = output.splitlines()
    important = [
        line[:300] for line in lines if re.search(r"(?i)error|failed|exception|warning", line)
    ][:10]
    return {
        "status": "pass" if exit_code == 0 else "fail" if exit_code == 1 else "infra",
        "exit_code": exit_code,
        "metrics": {"line_count": len(lines), "byte_count": len(raw)},
        "artifact_ref": ref,
        "sha256": digest,
        "expires_at": int(time.time()) + ttl_seconds,
        "summary": important,
    }


def read_artifact(
    root: str | Path, artifact_ref: str, *, offset: int = 0, limit: int = 100
) -> dict:
    if not re.fullmatch(r"tool-outputs/[0-9a-f]{64}\.log", artifact_ref):
        raise ValueError("INVALID_ARTIFACT_REF")
    if offset < 0 or not 1 <= limit <= 500:
        raise ValueError("INVALID_PAGE")
    base = Path(root).resolve()
    target = (base / artifact_ref).resolve()
    if not target.is_relative_to((base / "tool-outputs").resolve()) or not target.is_file():
        raise FileNotFoundError("ARTIFACT_NOT_FOUND")
    metadata = target.with_suffix(".meta")
    try:
        expires_at = int(metadata.read_text(encoding="ascii"))
    except (OSError, ValueError):
        raise FileNotFoundError("ARTIFACT_METADATA_MISSING") from None
    if expires_at <= int(time.time()):
        raise FileNotFoundError("ARTIFACT_EXPIRED")
    lines = target.read_text(errors="replace").splitlines()
    return {
        "lines": lines[offset : offset + limit],
        "offset": offset,
        "next_offset": min(offset + limit, len(lines)) if offset + limit < len(lines) else None,
    }
