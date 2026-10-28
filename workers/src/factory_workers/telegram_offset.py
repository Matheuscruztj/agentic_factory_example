"""Atomic Telegram update offset that survives worker restarts."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class TelegramOffsetStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> int:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return 0
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("TELEGRAM_OFFSET_UNREADABLE") from exc
        if (
            not isinstance(value, dict)
            or value.get("schema") != 1
            or type(value.get("offset")) is not int
            or value["offset"] < 0
        ):
            raise RuntimeError("TELEGRAM_OFFSET_INVALID")
        return value["offset"]

    def save(self, offset: int) -> None:
        if type(offset) is not int or offset < 0:
            raise ValueError("TELEGRAM_OFFSET_INVALID")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"schema": 1, "offset": offset}, separators=(",", ":"))
        fd, temporary = tempfile.mkstemp(prefix=".telegram-offset-", dir=self.path.parent)
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
