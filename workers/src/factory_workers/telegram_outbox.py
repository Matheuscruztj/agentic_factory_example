"""Durable, redacted Telegram replies delivered from the transactional outbox."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from integrations.telegram import TelegramError, TelegramNotifier, redact_telegram_text
from sqlalchemy import and_, exists, or_, select
from task_engine.models import Demand, EventInbox, EventOutbox, Task, TransitionEvent
from task_engine.outbox import enqueue_event

TELEGRAM_SEND_EVENT = "telegram.message.send"

_NOTIFIABLE_STATES = {
    "clarification_pending",
    "blocked",
    "failed",
    "human_review",
    "completed",
}


def enqueue_transition_notifications(session, *, limit: int = 100) -> int:
    """Turn persisted demand/task milestones into safe Telegram thread replies.

    Telegram intake stores its originating ``chat_id:message_id`` as the
    demand external identity. The stable transition ID is the outbox key, so
    repeatedly scanning the durable event log cannot create duplicate sends.
    Only a small allowlisted set of states is exposed; task output and model
    transcripts are never copied into a Telegram message.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("TELEGRAM_OUTBOX_LIMIT_INVALID")
    transitions = session.scalars(
        select(TransitionEvent)
        .where(
            TransitionEvent.to_state.in_(_NOTIFIABLE_STATES),
            ~exists().where(EventOutbox.event_id == ("telegram-transition:" + TransitionEvent.id)),
            or_(
                and_(
                    TransitionEvent.entity_type == "demand",
                    exists().where(
                        Demand.id == TransitionEvent.entity_id,
                        Demand.source == "telegram",
                    ),
                ),
                and_(
                    TransitionEvent.entity_type == "task",
                    exists().where(
                        Task.id == TransitionEvent.entity_id,
                        Task.demand_id == Demand.id,
                        Demand.source == "telegram",
                    ),
                ),
            ),
        )
        .order_by(TransitionEvent.created_at, TransitionEvent.id)
        .limit(limit)
    ).all()
    queued = 0
    for transition in transitions:
        if transition.entity_type == "demand":
            demand = session.get(Demand, transition.entity_id)
        elif transition.entity_type == "task":
            task = session.get(Task, transition.entity_id)
            demand = session.get(Demand, task.demand_id) if task is not None else None
        else:
            continue
        if demand is None or demand.source != "telegram":
            continue
        try:
            raw_chat, raw_message = demand.external_id.split(":", 1)
            chat_id, reply_to_message_id = int(raw_chat), int(raw_message)
        except (AttributeError, TypeError, ValueError):
            continue
        if chat_id <= 0 or reply_to_message_id <= 0:
            continue
        reference = f"DEMAND-{demand.id}"
        text = f"{reference}: status atualizado para {transition.to_state}."
        if transition.to_state == "completed":
            text = (
                f"{reference}: execução concluída; consulte a interface autenticada "
                "para os detalhes."
            )
        elif transition.to_state == "human_review":
            text = f"{reference}: aguardando revisão; consulte a interface autenticada."
        event_id = f"telegram-transition:{transition.id}"
        exists_already = session.scalar(
            select(EventOutbox.id).where(EventOutbox.event_id == event_id)
        )
        enqueue_telegram_message(
            session,
            event_id=event_id,
            chat_id=chat_id,
            reply_to_message_id=reply_to_message_id,
            text=text,
        )
        if exists_already is None:
            queued += 1
    return queued


def enqueue_telegram_message(
    session,
    *,
    event_id: str,
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
) -> EventOutbox:
    """Persist a stable outbound event; repeated matching event IDs are harmless."""
    if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 160:
        raise ValueError("TELEGRAM_EVENT_ID_INVALID")
    if type(chat_id) is not int:
        raise TelegramError("CHAT_NOT_ALLOWED")
    if reply_to_message_id is not None and (
        type(reply_to_message_id) is not int or reply_to_message_id < 1
    ):
        raise TelegramError("REPLY_REFERENCE_INVALID")
    payload = {
        "chat_id": chat_id,
        "text": redact_telegram_text(text),
        "reply_to_message_id": reply_to_message_id,
    }
    return enqueue_event(session, event_id, TELEGRAM_SEND_EVENT, payload)


def dispatch_pending_telegram(
    session_factory,
    notifier: TelegramNotifier,
    *,
    limit: int = 50,
    allowed_roots: set[tuple[int, int]] | None = None,
    allowed_event_ids: set[str] | None = None,
) -> dict[str, int]:
    """Send pending Telegram outbox events and record attempts atomically.

    Database row locks serialize competing dispatchers on PostgreSQL. Provider
    delivery remains at least once: a process crash after Telegram accepts a
    message but before the database commit can cause a retry. Telegram's send
    API does not provide a client idempotency key, so callers must use stable
    event IDs and avoid claiming exactly-once external delivery.
    """
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("TELEGRAM_OUTBOX_LIMIT_INVALID")
    if allowed_roots is not None and not allowed_roots:
        return {"sent": 0, "failed": 0}
    if allowed_event_ids is not None and not allowed_event_ids:
        return {"sent": 0, "failed": 0}
    sent = failed = 0
    with session_factory() as session:
        with session.begin():
            enqueue_transition_notifications(session)
            rows = session.scalars(
                select(EventOutbox)
                .where(
                    EventOutbox.event_type == TELEGRAM_SEND_EVENT,
                    EventOutbox.published_at.is_(None),
                    *(
                        [EventOutbox.event_id.in_(sorted(allowed_event_ids))]
                        if allowed_event_ids is not None
                        else []
                    ),
                    *(
                        [
                            or_(
                                *[
                                    and_(
                                        EventOutbox.payload["chat_id"].as_integer() == chat,
                                        EventOutbox.payload["reply_to_message_id"].as_integer()
                                        == message,
                                    )
                                    for chat, message in sorted(allowed_roots)
                                ]
                            )
                        ]
                        if allowed_roots is not None
                        else []
                    ),
                )
                .order_by(EventOutbox.created_at, EventOutbox.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            for row in rows:
                payload = row.payload
                receipt_id = f"telegram-delivered:{row.event_id}"
                receipt = session.get(EventInbox, receipt_id)
                if receipt is not None:
                    # Reconcile a previously recorded provider receipt without
                    # sending the message again if the outbox row was reset.
                    row.published_at = datetime.now(UTC)
                    continue
                try:
                    if (
                        not isinstance(payload, dict)
                        or type(payload.get("chat_id")) is not int
                        or not isinstance(payload.get("text"), str)
                    ):
                        raise TelegramError("TELEGRAM_OUTBOX_PAYLOAD_INVALID")
                    reply_id = payload.get("reply_to_message_id")
                    if reply_id is not None and (type(reply_id) is not int or reply_id < 1):
                        raise TelegramError("REPLY_REFERENCE_INVALID")
                    delivery = notifier.send_message(
                        chat_id=payload["chat_id"],
                        text=payload["text"],
                        reply_to_message_id=reply_id,
                    )
                    message_id = delivery.get("message_id") if isinstance(delivery, dict) else None
                    if type(message_id) is not int or message_id < 1:
                        raise TelegramError("TELEGRAM_SEND_RESPONSE_INVALID")
                except TelegramError:
                    row.attempts += 1
                    failed += 1
                    continue
                row.published_at = datetime.now(UTC)
                row.attempts += 1
                session.add(
                    EventInbox(
                        event_id=receipt_id,
                        result={
                            "outbox_event_id": row.event_id,
                            "message_id": message_id,
                            "reply_to_message_id": reply_id,
                            "destination_sha256": hashlib.sha256(
                                str(payload["chat_id"]).encode()
                            ).hexdigest(),
                            "redaction_applied": True,
                        },
                    )
                )
                sent += 1
    return {"sent": sent, "failed": failed}
