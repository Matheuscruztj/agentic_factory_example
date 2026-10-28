"""Atomic file-backed GitHub polling cursor, safe across worker restarts."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path


class JsonCursorStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> datetime | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("GITHUB_CURSOR_UNREADABLE") from exc
        if not isinstance(payload, dict) or payload.get("schema") != 1:
            raise RuntimeError("GITHUB_CURSOR_INVALID")
        value = payload.get("updated_at")
        if not isinstance(value, str):
            raise RuntimeError("GITHUB_CURSOR_INVALID")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError("GITHUB_CURSOR_INVALID") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise RuntimeError("GITHUB_CURSOR_INVALID")
        return parsed.astimezone(UTC)

    def save(self, cursor: datetime) -> None:
        if cursor.tzinfo is None or cursor.utcoffset() is None:
            raise ValueError("CURSOR_MUST_BE_TIMEZONE_AWARE")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"schema": 1, "updated_at": cursor.astimezone(UTC).isoformat()},
            separators=(",", ":"),
        )
        fd, temporary = tempfile.mkstemp(prefix=".github-cursor-", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
