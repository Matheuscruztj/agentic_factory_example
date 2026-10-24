"""Normalize untrusted inbound messages and reconcile them idempotently."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.models import Demand, EventInbox
from task_engine.requirements import create_demand

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_VALID_TYPES = {"bug", "feature", "maintenance", "question"}


class IntakeError(ValueError):
    """Stable validation errors for external intake payloads."""


@dataclass(frozen=True, slots=True)
class Attachment:
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class IntakeMessage:
    source: str
    external_id: str
    url: str | None
    author: str
    title: str
    text: str
    demand_type: str = "question"
    attachments: tuple[Attachment, ...] = ()

    @property
    def event_id(self) -> str:
        identity = f"{self.source}:{self.external_id}".encode()
        return f"intake:{hashlib.sha256(identity).hexdigest()}"


def _clean(value: str, *, field: str, limit: int, required: bool = True) -> str:
    cleaned = _CONTROL_CHARS.sub("", value).strip()
    if required and not cleaned:
        raise IntakeError(f"{field.upper()}_REQUIRED")
    if len(cleaned) > limit:
        raise IntakeError(f"{field.upper()}_TOO_LONG")
    return cleaned


def _safe_url(value: str, *, field: str) -> str:
    cleaned = _clean(value, field=field, limit=2048)
    parsed = urlsplit(cleaned)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise IntakeError(f"INVALID_{field.upper()}")
    return cleaned


def normalize_intake(payload: dict[str, object]) -> IntakeMessage:
    """Validate and bound a provider payload; message text remains untrusted data."""
    try:
        source = _clean(str(payload["source"]), field="source", limit=32).lower()
        external_id = _clean(str(payload["external_id"]), field="external_id", limit=160)
        author = _clean(str(payload.get("author", "unknown")), field="author", limit=160)
        title = _clean(str(payload["title"]), field="title", limit=240)
        content = _clean(str(payload["text"]), field="text", limit=20000)
        demand_type = _clean(
            str(payload.get("demand_type", "question")), field="demand_type", limit=32
        ).lower()
    except KeyError as exc:
        raise IntakeError(f"{exc.args[0].upper()}_REQUIRED") from None
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", source):
        raise IntakeError("INVALID_SOURCE")
    if demand_type not in _VALID_TYPES:
        raise IntakeError("INVALID_DEMAND_TYPE")
    raw_url = payload.get("url")
    url = _safe_url(str(raw_url), field="url") if raw_url is not None else None
    raw_attachments = payload.get("attachments", ())
    if not isinstance(raw_attachments, (list, tuple)) or len(raw_attachments) > 20:
        raise IntakeError("INVALID_ATTACHMENTS")
    attachments: list[Attachment] = []
    for item in raw_attachments:
        if not isinstance(item, dict) or "name" not in item or "url" not in item:
            raise IntakeError("INVALID_ATTACHMENT")
        attachments.append(
            Attachment(
                name=_clean(str(item["name"]), field="attachment_name", limit=200),
                url=_safe_url(str(item["url"]), field="attachment_url"),
            )
        )
    return IntakeMessage(
        source, external_id, url, author, title, content, demand_type, tuple(attachments)
    )


def reconcile_intake(session: Session, message: IntakeMessage) -> tuple[Demand, bool]:
    """Create a demand once, or refresh its source event without duplicating it."""
    payload = {
        "source": message.source,
        "external_id": message.external_id,
        "url": message.url,
        "author": message.author,
        "title": message.title,
        "text": message.text,
        "demand_type": message.demand_type,
        "attachments": [{"name": item.name, "url": item.url} for item in message.attachments],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    event = session.get(EventInbox, message.event_id)
    existing = session.scalar(
        select(Demand).where(
            Demand.source == message.source, Demand.external_id == message.external_id
        )
    )
    created = existing is None
    if existing is None:
        existing = create_demand(
            session,
            source=message.source,
            external_id=message.external_id,
            title=message.title,
            demand_type=message.demand_type,
        )
    else:
        existing.title = message.title
        existing.demand_type = message.demand_type
    if event is None:
        event = EventInbox(event_id=message.event_id, result={})
        session.add(event)
    event.result = {
        "demand_id": existing.id,
        "payload_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "source_url": message.url,
        "author": message.author,
        "text": message.text,
        "attachments": payload["attachments"],
    }
    session.flush()
    return existing, created
