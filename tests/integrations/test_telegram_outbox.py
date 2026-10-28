from __future__ import annotations

import hashlib
from pathlib import Path

from factory_workers.telegram_outbox import (
    TELEGRAM_SEND_EVENT,
    dispatch_pending_telegram,
    enqueue_telegram_message,
    enqueue_transition_notifications,
)
from integrations.provider_simulator import LocalProviderSimulator, ProviderFault
from integrations.telegram import TelegramNotifier
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import Demand, EventInbox, EventOutbox, Task, TransitionEvent


def _sessions(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'telegram-outbox.db'}")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _notifier(simulator: LocalProviderSimulator) -> TelegramNotifier:
    return TelegramNotifier(
        token="123:fake-token",
        allowed_chats={77},
        enabled=True,
        request=simulator.telegram_request,
    )


def test_per_demand_authorization_never_drains_another_thread(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        for message_id in (12, 13):
            enqueue_telegram_message(
                session,
                event_id=f"scoped:{message_id}",
                chat_id=77,
                reply_to_message_id=message_id,
                text="Safe progress",
            )
    simulator = LocalProviderSimulator()
    assert dispatch_pending_telegram(sessions, _notifier(simulator), allowed_roots=set()) == {
        "sent": 0,
        "failed": 0,
    }
    assert dispatch_pending_telegram(sessions, _notifier(simulator), allowed_roots={(77, 13)}) == {
        "sent": 1,
        "failed": 0,
    }
    assert len(simulator.telegram_messages) == 1
    assert simulator.telegram_messages[0]["reply_to_message_id"] == 13
    with sessions() as session:
        pending = session.scalar(select(EventOutbox).where(EventOutbox.event_id == "scoped:12"))
        assert pending.published_at is None and pending.attempts == 0
    engine.dispose()


def test_event_authorization_dispatches_only_selected_event_on_same_thread(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        for event_id in ("old:blocked:1", "old:blocked:2", "current:human-review"):
            enqueue_telegram_message(
                session,
                event_id=event_id,
                chat_id=77,
                reply_to_message_id=13,
                text=event_id,
            )

    simulator = LocalProviderSimulator()
    assert dispatch_pending_telegram(
        sessions,
        _notifier(simulator),
        allowed_roots={(77, 13)},
        allowed_event_ids={"current:human-review"},
    ) == {"sent": 1, "failed": 0}
    assert [message["text"] for message in simulator.telegram_messages] == [
        "current:human-review"
    ]
    with sessions() as session:
        for event_id in ("old:blocked:1", "old:blocked:2"):
            row = session.scalar(
                select(EventOutbox).where(EventOutbox.event_id == event_id)
            )
            assert row is not None and row.published_at is None and row.attempts == 0
    engine.dispose()


def test_outbox_redacts_before_persist_and_deduplicates_event_id(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        first = enqueue_telegram_message(
            session,
            event_id="demand:abc:question:1",
            chat_id=77,
            reply_to_message_id=12,
            text="Use token=supersecret and email person@example.org",
        )
        replay = enqueue_telegram_message(
            session,
            event_id="demand:abc:question:1",
            chat_id=77,
            reply_to_message_id=12,
            text="Use token=supersecret and email person@example.org",
        )
        assert first.id == replay.id
        assert "supersecret" not in str(first.payload)
        assert "person@example.org" not in str(first.payload)

    simulator = LocalProviderSimulator()
    result = dispatch_pending_telegram(sessions, _notifier(simulator))
    assert result == {"sent": 1, "failed": 0}
    assert simulator.telegram_messages[0]["chat_id"] == 77
    assert simulator.telegram_messages[0]["reply_to_message_id"] == 12
    assert "[REDACTED]" in simulator.telegram_messages[0]["text"]
    with sessions() as session:
        row = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == "demand:abc:question:1")
        )
        assert row is not None and row.event_type == TELEGRAM_SEND_EVENT
        assert row.published_at is not None and row.attempts == 1
        receipt = session.get(EventInbox, "telegram-delivered:demand:abc:question:1")
        assert receipt is not None
        assert receipt.result == {
            "outbox_event_id": "demand:abc:question:1",
            "message_id": 1,
            "reply_to_message_id": 12,
            "destination_sha256": hashlib.sha256(b"77").hexdigest(),
            "redaction_applied": True,
        }
    assert dispatch_pending_telegram(sessions, _notifier(simulator)) == {"sent": 0, "failed": 0}
    assert len(simulator.telegram_messages) == 1
    with sessions.begin() as session:
        row = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == "demand:abc:question:1")
        )
        assert row is not None
        row.published_at = None
    assert dispatch_pending_telegram(sessions, _notifier(simulator)) == {"sent": 0, "failed": 0}
    assert len(simulator.telegram_messages) == 1
    with sessions() as session:
        row = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == "demand:abc:question:1")
        )
        assert row is not None and row.published_at is not None and row.attempts == 1
    engine.dispose()


def test_outbox_failed_delivery_remains_pending_and_retries(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        enqueue_telegram_message(
            session,
            event_id="demand:abc:progress:2",
            chat_id=77,
            reply_to_message_id=13,
            text="Progress update",
        )

    simulator = LocalProviderSimulator()
    simulator.fail_once(ProviderFault("telegram:sendMessage", status=429))
    notifier = _notifier(simulator)
    assert dispatch_pending_telegram(sessions, notifier) == {"sent": 0, "failed": 1}
    with sessions() as session:
        row = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == "demand:abc:progress:2")
        )
        assert row is not None and row.published_at is None and row.attempts == 1

    assert dispatch_pending_telegram(sessions, notifier) == {"sent": 1, "failed": 0}
    assert simulator.telegram_messages[0]["text"] == "Progress update"
    assert simulator.telegram_messages[0]["reply_to_message_id"] == 13
    with sessions() as session:
        row = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == "demand:abc:progress:2")
        )
        assert row is not None and row.published_at is not None and row.attempts == 2
    engine.dispose()


def test_demand_milestones_become_redacted_idempotent_thread_replies(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        demand = Demand(
            id="demand-telegram-1",
            source="telegram",
            external_id="77:12",
            title="Synthetic request",
            demand_type="feature",
            status="completed",
        )
        unrelated = Demand(
            id="demand-manual-1",
            source="manual",
            external_id="manual-1",
            title="Local request",
            demand_type="feature",
            status="completed",
        )
        session.add_all([demand, unrelated])
        session.flush()
        task = Task(
            id="task-telegram-1",
            demand_id=demand.id,
            title="Sensitive task title",
            owner_role="backend",
            status="failed",
            result={"transcript": "do not disclose secret=fixture-secret"},
        )
        session.add(task)
        session.flush()
        session.add_all(
            [
                TransitionEvent(
                    id="transition-telegram-1",
                    entity_type="demand",
                    entity_id=demand.id,
                    from_state="human_review",
                    to_state="completed",
                    expected_version=1,
                    actor="system",
                    reason="synthetic test",
                    idempotency_key="complete-1",
                ),
                TransitionEvent(
                    id="transition-manual-1",
                    entity_type="demand",
                    entity_id=unrelated.id,
                    from_state="human_review",
                    to_state="completed",
                    expected_version=1,
                    actor="system",
                    reason="synthetic test",
                    idempotency_key="complete-2",
                ),
                TransitionEvent(
                    id="transition-task-1",
                    entity_type="task",
                    entity_id=task.id,
                    from_state="running",
                    to_state="failed",
                    expected_version=1,
                    actor="system",
                    reason="synthetic test",
                    idempotency_key="failed-1",
                ),
            ]
        )
        session.flush()
        assert enqueue_transition_notifications(session) == 2
        assert enqueue_transition_notifications(session) == 0

    simulator = LocalProviderSimulator()
    assert dispatch_pending_telegram(sessions, _notifier(simulator)) == {
        "sent": 2,
        "failed": 0,
    }
    sent = next(msg for msg in simulator.telegram_messages if "concluída" in msg["text"])
    assert sent["chat_id"] == 77
    assert sent["reply_to_message_id"] == 12
    assert "DEMAND-demand-telegram-1" in sent["text"]
    assert "interface autenticada" in sent["text"]
    assert "Synthetic request" not in sent["text"]
    assert all("fixture-secret" not in msg["text"] for msg in simulator.telegram_messages)
    assert all(msg["reply_to_message_id"] == 12 for msg in simulator.telegram_messages)
    assert dispatch_pending_telegram(sessions, _notifier(simulator)) == {
        "sent": 0,
        "failed": 0,
    }
    assert len(simulator.telegram_messages) == 2
    engine.dispose()
