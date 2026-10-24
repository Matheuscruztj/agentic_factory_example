"""Transactional outbox/inbox helpers. Publish callbacks run only after commit."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from task_engine.models import EventInbox, EventOutbox


def enqueue_event(session: Session, event_id: str, event_type: str, payload: dict) -> EventOutbox:
    existing = session.scalar(select(EventOutbox).where(EventOutbox.event_id == event_id))
    if existing:
        if existing.event_type != event_type or existing.payload != payload:
            raise ValueError("EVENT_ID_REUSED")
        return existing
    event = EventOutbox(event_id=event_id, event_type=event_type, payload=payload)
    session.add(event)
    session.flush()
    return event


def consume_once(session: Session, event_id: str, handler: Callable[[], dict]) -> tuple[bool, dict]:
    """Record delivery and domain side effect in the caller's same transaction."""
    existing = session.get(EventInbox, event_id)
    if existing:
        return False, existing.result
    result = handler()
    row = EventInbox(event_id=event_id, result=result)
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = session.get(EventInbox, event_id)
        if existing:
            return False, existing.result
        raise
    return True, result


def publish_pending(
    session_factory, publisher: Callable[[str, str, dict], None], *, limit: int = 100
) -> int:
    """At-least-once delivery: mark published only after callback succeeds."""
    sent = 0
    with session_factory() as session:
        rows = session.scalars(
            select(EventOutbox)
            .where(EventOutbox.published_at.is_(None))
            .order_by(EventOutbox.created_at)
            .limit(limit)
        ).all()
        events = [(row.id, row.event_id, row.event_type, row.payload) for row in rows]
    for row_id, event_id, event_type, payload in events:
        try:
            publisher(event_id, event_type, payload)
        except Exception:
            with session_factory.begin() as session:
                row = session.get(EventOutbox, row_id)
                if row and row.published_at is None:
                    row.attempts += 1
            continue
        with session_factory.begin() as session:
            row = session.get(EventOutbox, row_id)
            if row and row.published_at is None:
                row.published_at = datetime.now(UTC)
                row.attempts += 1
                sent += 1
    return sent
