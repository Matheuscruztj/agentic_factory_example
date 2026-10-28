from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from factory_workers.telegram_commands import telegram_command_handler
from factory_workers.telegram_offset import TelegramOffsetStore
from factory_workers.telegram_poll import poll_telegram_into_database
from integrations.telegram import TelegramError, parse_telegram_command
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import ApprovalRequest, AuditRecord, Demand, EventInbox, EventOutbox


def _sessions(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'telegram-commands.db'}")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _message(update_id: int = 100, user_id: int = 7001) -> dict:
    return {
        "_update_id": update_id,
        "message_id": update_id + 1,
        "chat": {"id": 8001},
        "from": {"id": user_id},
    }


def test_telegram_approval_commands_require_exact_uuid_and_hash():
    approval_id = str(uuid.uuid4())
    command = parse_telegram_command(f"/aprovar {approval_id} {'a' * 64}")
    assert command.action == "approve"
    assert command.approval_id == approval_id
    assert command.payload_hash == "a" * 64
    assert parse_telegram_command("/aprovacoes").action == "approvals"
    assert parse_telegram_command(f"/progresso DEMAND-{'b' * 8}").action == "status"
    with pytest.raises(TelegramError, match="APPROVAL_SYNTAX_INVALID"):
        parse_telegram_command(f"/aprovar {approval_id} stale")
    assert parse_telegram_command("aprovo esta mensagem").action == "demand"


def test_telegram_approval_is_forwarded_to_authenticated_ui(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        demand = Demand(
            source="manual",
            external_id="telegram-approval-case",
            title="Synthetic approval",
            demand_type="feature",
            status="triage",
        )
        session.add(demand)
        session.flush()
        from factory_api.routers.approvals import current_entity

        _, version, digest, _ = current_entity(session, "demand", demand.id)
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            entity_type="demand",
            entity_id=demand.id,
            entity_version=version,
            payload_hash=digest,
            status="pending",
            requested_by="agent",
        )
        session.add(approval)

    command = parse_telegram_command(f"/aprovar {approval.id} {approval.payload_hash}")
    with sessions.begin() as session:
        result = telegram_command_handler({7001})(session, _message(), command)
        assert result == {"status": "handled", "action": "approve"}

    with sessions() as session:
        stored = session.get(ApprovalRequest, approval.id)
        assert stored is not None
        assert stored.status == "pending"
        assert stored.decision_by is None
        event = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == f"approval-decided:{approval.id}")
        )
        assert event is None
        audit = session.scalar(
            select(AuditRecord).where(
                AuditRecord.subject_id == approval.id,
                AuditRecord.action == "approval.decided",
            )
        )
        assert audit is None
        reply = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == "telegram-command-response:100")
        )
        assert reply is not None
        assert reply.payload["reply_to_message_id"] == 101
        assert "interface autenticada" in reply.payload["text"]
        assert "http://localhost:5173/?tab=approvals" in reply.payload["text"]

    with sessions.begin() as session:
        telegram_command_handler({7001})(session, _message(update_id=101), command)
    with sessions() as session:
        decisions = session.scalars(
            select(AuditRecord).where(
                AuditRecord.subject_id == approval.id,
                AuditRecord.action == "approval.decided",
            )
        ).all()
        assert len(decisions) == 0
    engine.dispose()


def test_telegram_approval_rejects_unlisted_identity_and_stale_hash(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        demand = Demand(
            source="manual",
            external_id="telegram-approval-stale",
            title="Synthetic stale approval",
            demand_type="feature",
            status="triage",
        )
        session.add(demand)
        session.flush()
        from factory_api.routers.approvals import current_entity

        _, version, digest, _ = current_entity(session, "demand", demand.id)
        approval = ApprovalRequest(
            id=str(uuid.uuid4()), entity_type="demand", entity_id=demand.id,
            entity_version=version, payload_hash=digest, status="pending", requested_by="agent",
        )
        session.add(approval)
    handler = telegram_command_handler({7001})
    stale = parse_telegram_command(f"/aprovar {approval.id} {'0' * 64}")
    with sessions.begin() as session:
        handler(session, _message(), stale)
    with sessions() as session:
        assert session.get(ApprovalRequest, approval.id).status == "pending"
    unauthorized = parse_telegram_command(f"/aprovar {approval.id} {approval.payload_hash}")
    with sessions() as session:
        with pytest.raises(PermissionError, match="TELEGRAM_OPERATOR_NOT_ALLOWED"):
            handler(session, _message(update_id=101, user_id=9999), unauthorized)
    engine.dispose()


def test_intake_worker_commits_approval_and_reply_with_idempotent_update(tmp_path):
    engine, sessions = _sessions(tmp_path)
    with sessions.begin() as session:
        demand = Demand(
            source="manual",
            external_id="telegram-worker-approval",
            title="Worker approval integration",
            demand_type="feature",
            status="triage",
        )
        session.add(demand)
        session.flush()
        from factory_api.routers.approvals import current_entity

        _, version, digest, _ = current_entity(session, "demand", demand.id)
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            entity_type="demand",
            entity_id=demand.id,
            entity_version=version,
            payload_hash=digest,
            status="pending",
            requested_by="agent",
        )
        session.add(approval)

    update_id = 500
    message = {
        **_message(update_id),
        "text": f"/aprovar {approval.id} {approval.payload_hash}",
    }

    class OneUpdatePoller:
        def poll_once(self, *, offset, process, timeout, persist_offset):
            process({**message, "_update_id": update_id})
            persist_offset(max(offset, update_id + 1))
            return max(offset, update_id + 1)

    offsets = TelegramOffsetStore(tmp_path / "offset.json")
    first = poll_telegram_into_database(
        OneUpdatePoller(),
        session_factory=sessions,
        offset_store=offsets,
        command_handler=telegram_command_handler({7001}),
    )
    assert first == {"status": "pass", "imported": 1, "offset": 501}
    replay = poll_telegram_into_database(
        OneUpdatePoller(),
        session_factory=sessions,
        offset_store=offsets,
        command_handler=telegram_command_handler({7001}),
    )
    assert replay == {"status": "pass", "imported": 1, "offset": 501}
    with sessions() as session:
        assert session.get(ApprovalRequest, approval.id).status == "pending"
        assert session.get(EventInbox, f"telegram-update:{update_id}") is not None
        assert session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == f"approval-decided:{approval.id}")
        ) is None
        assert len(
            session.scalars(
                select(AuditRecord).where(
                    AuditRecord.subject_id == approval.id,
                    AuditRecord.action == "approval.decided",
                )
            ).all()
        ) == 0
        assert len(
            session.scalars(
                select(EventOutbox).where(
                    EventOutbox.event_id == f"telegram-command-response:{update_id}"
                )
            ).all()
        ) == 1
    engine.dispose()
