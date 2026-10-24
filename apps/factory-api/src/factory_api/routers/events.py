from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, tuple_
from task_engine.models import AuditRecord, TransitionEvent

from factory_api.database import SessionFactory
from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/events", tags=["events"], dependencies=[Depends(require_operator)]
)


def _decode_cursor(value: str | None) -> dict[str, tuple[datetime | None, str]]:
    empty = {"audit": (None, ""), "transition": (None, "")}
    if not value:
        return empty
    try:
        raw = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        for source in empty:
            if raw.get(source):
                empty[source] = (datetime.fromisoformat(raw[source][0]), raw[source][1])
        return empty
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {"audit": (None, ""), "transition": (None, "")}


def _encode_cursor(cursors: dict[str, tuple[datetime | None, str]]) -> str:
    value = json.dumps(
        {
            source: [at.isoformat(), row_id] if at else None
            for source, (at, row_id) in cursors.items()
        },
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _load_events(
    cursors: dict[str, tuple[datetime | None, str]], limit: int = 50
) -> list[tuple[datetime, str, str, dict]]:
    audit_after, audit_id = cursors["audit"]
    transition_after, transition_id = cursors["transition"]
    with SessionFactory() as session:
        audit_query = select(AuditRecord).order_by(AuditRecord.created_at, AuditRecord.id)
        transition_query = select(TransitionEvent).order_by(
            TransitionEvent.created_at, TransitionEvent.id
        )
        if audit_after:
            audit_query = audit_query.where(
                tuple_(AuditRecord.created_at, AuditRecord.id) > (audit_after, audit_id)
            )
        if transition_after:
            transition_query = transition_query.where(
                tuple_(TransitionEvent.created_at, TransitionEvent.id)
                > (transition_after, transition_id)
            )
        audits = session.scalars(audit_query.limit(limit)).all()
        transitions = session.scalars(transition_query.limit(limit)).all()
    values = [
        (
            row.created_at,
            row.id,
            "audit",
            {
                "type": "audit",
                "subject_type": row.subject_type,
                "subject_id": row.subject_id,
                "action": row.action,
            },
        )
        for row in audits
    ]
    values.extend(
        (
            row.created_at,
            row.id,
            "transition",
            {
                "type": "transition",
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "from_state": row.from_state,
                "to_state": row.to_state,
            },
        )
        for row in transitions
    )
    return sorted(values, key=lambda item: (item[0], item[1], item[2]))[:limit]


@router.get("/stream")
async def event_stream(
    request: Request, last_event_id: str | None = Header(default=None, alias="Last-Event-ID")
):
    async def generate():
        cursors = _decode_cursor(last_event_id)
        while not await request.is_disconnected():
            events = _load_events(cursors)
            if events:
                for created_at, event_id, source, data in events:
                    cursors[source] = (created_at, event_id)
                    encoded = _encode_cursor(cursors)
                    body = json.dumps(data, separators=(",", ":"))
                    yield f"id: {encoded}\nevent: update\ndata: {body}\n\n"
            else:
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
