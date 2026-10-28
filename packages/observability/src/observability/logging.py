"""Small JSON logger with correlation fields and recursive secret masking."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from observability.redaction import redact_fields


class CorrelationContext:
    """Mutable per-request context that services can pass through worker boundaries."""

    def __init__(self, correlation_id: str | None = None, task_id: str | None = None) -> None:
        self.correlation_id = correlation_id or str(uuid4())
        self.task_id = task_id

    def bind_task(self, task_id: str) -> None:
        self.task_id = task_id

    def fields(self) -> dict[str, str]:
        result = {"correlation_id": self.correlation_id}
        if self.task_id:
            result["task_id"] = self.task_id
        return result


def log_record(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **redact_fields(fields),
    }
    logger.log(level, json.dumps(record, sort_keys=True, separators=(",", ":")))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        supplied = getattr(record, "fields", None)
        if isinstance(supplied, Mapping):
            payload.update(redact_fields(supplied))
        else:
            payload["message"] = redact_fields({"message": payload["message"]})["message"]
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
