from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from factory_workers.github_poll import poll_github
from factory_workers.telegram_offset import TelegramOffsetStore
from factory_workers.telegram_poll import poll_telegram_into_database
from integrations.github import GitHubClient, GitHubError
from integrations.telegram import TelegramError, TelegramPoller, telegram_message_to_intake
from shared_contracts.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from task_engine.models import Demand
from task_engine.refinement import refine_requirement
from task_engine.requirements import decide_revision, edit_revision


def test_github_client_pins_repository_filters_prs_and_rejects_arbitrary_paths() -> None:
    calls = []

    def request(url, headers):
        calls.append((url, headers))
        return 200, [{"number": 1}, {"number": 2, "pull_request": {}}], {}

    client = GitHubClient(owner="acme", repo="factory", token="fake", request=request)
    assert client.list_issues() == [{"number": 1}]
    assert calls[0][0].startswith("https://api.github.com/repos/acme/factory/issues?")
    assert "state=all" in calls[0][0]
    with pytest.raises(GitHubError, match="INVALID_API_PATH"):
        client.get("../../users")


def test_github_client_verifies_access_for_the_configured_repository_only() -> None:
    seen = []

    def request(url, headers):
        seen.append(url)
        return 200, {"full_name": "ACME/Factory", "private": True}, {}

    client = GitHubClient(owner="acme", repo="factory", token="fake", request=request)
    assert client.verify_repository_access() == {
        "repository": "acme/factory",
        "private": True,
        "read_access": True,
    }
    assert seen == ["https://api.github.com/repos/acme/factory"]

    wrong_repo = GitHubClient(
        owner="acme",
        repo="factory",
        token="fake",
        request=lambda _url, _headers: (200, {"full_name": "acme/other"}, {}),
    )
    with pytest.raises(GitHubError, match="REPOSITORY_IDENTITY_MISMATCH"):
        wrong_repo.verify_repository_access()


def test_github_poll_replay_is_idempotent_and_cursor_advances_only_after_success() -> None:
    now = datetime(2026, 10, 24, tzinfo=UTC)
    previous = now - timedelta(hours=1)

    class Client:
        def __init__(self):
            self.calls = []

        def list_issues(self, *, page, since):
            self.calls.append((page, since))
            return [{"number": 7, "updated_at": now.isoformat()}] if page == 1 else []

    client = Client()
    imported, saved = set(), []

    def import_once(issue):
        imported.add(issue["number"])

    result = poll_github(
        client,
        load_cursor=lambda: previous,
        save_cursor=saved.append,
        import_issue=import_once,
        now=now,
    )
    assert result["imported"] == 1 and len(imported) == 1
    assert client.calls[0][1].endswith("Z") and saved == [now]

    class BrokenClient:
        def list_issues(self, *, page, since):
            raise RuntimeError("page outage")

    with pytest.raises(RuntimeError, match="page outage"):
        poll_github(
            BrokenClient(),
            load_cursor=lambda: previous,
            save_cursor=lambda _cursor: pytest.fail("cursor advanced"),
            import_issue=lambda _issue: None,
            now=now,
        )


def test_telegram_allowlist_mapping_and_offset_are_post_processing() -> None:
    update = {
        "update_id": 10,
        "message": {
            "message_id": 5,
            "text": "Bug report",
            "chat": {"id": 22},
            "from": {"id": 33, "username": "tester"},
        },
    }
    poller = TelegramPoller(
        token="123456:fake_token",
        allowed_chats={22},
        allowed_users={33},
        enabled=True,
        request=lambda _method, _params: {"result": [update]},
    )
    stored = []
    next_offset = poller.poll_once(
        offset=0, process=lambda _message: None, persist_offset=stored.append
    )
    assert next_offset == 11
    assert stored == [11]
    mapped = telegram_message_to_intake(update["message"])
    assert mapped["source"] == "telegram" and mapped["external_id"] == "22:5"
    stored.clear()
    with pytest.raises(RuntimeError, match="process failure"):
        poller.poll_once(
            offset=0,
            process=lambda _message: (_ for _ in ()).throw(RuntimeError("process failure")),
            persist_offset=stored.append,
        )
    assert stored == []
    with pytest.raises(TelegramError, match="ALLOWLIST_REQUIRED"):
        TelegramPoller(
            token="123456:fake_token", allowed_chats=set(), allowed_users={33}, enabled=True
        )
    with pytest.raises(TelegramError, match="TELEGRAM_INTAKE_DISABLED"):
        TelegramPoller(
            token="123456:fake_token", allowed_chats={22}, allowed_users={33}, enabled=False
        )


def test_telegram_poll_persists_demand_and_restart_offset_idempotently(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'telegram.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    update = {
        "update_id": 10,
        "message": {
            "message_id": 5,
            "text": "Bug report",
            "chat": {"id": 22},
            "from": {"id": 33, "username": "tester"},
        },
    }
    poller = TelegramPoller(
        token="123456:fake_token",
        allowed_chats={22},
        allowed_users={33},
        enabled=True,
        request=lambda _method, _params: {"result": [update]},
    )
    offsets = TelegramOffsetStore(tmp_path / "telegram-offset.json")

    first = poll_telegram_into_database(poller, session_factory=sessions, offset_store=offsets)
    second = poll_telegram_into_database(poller, session_factory=sessions, offset_store=offsets)

    with sessions() as session:
        assert session.query(Demand).count() == 1
        from task_engine.models import EventInbox, EventOutbox

        inbox = session.get(EventInbox, "telegram-update:10")
        assert inbox is not None
        assert inbox.result["demand_id"]
        ack = session.query(EventOutbox).filter_by(
            event_id=f"telegram-demand-ack:{inbox.result['demand_id']}"
        ).one()
        assert ack.payload["chat_id"] == 22
        assert ack.payload["reply_to_message_id"] == 5
        assert ack.payload["text"].startswith("Demanda recebida e registrada.")
    assert first == {"status": "pass", "imported": 1, "offset": 11}
    assert second["offset"] == 11
    assert offsets.load() == 11
    assert (tmp_path / "telegram-offset.json").stat().st_mode & 0o777 == 0o600
    engine.dispose()


def test_telegram_non_text_is_journaled_and_does_not_block_offset(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'telegram-failure.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    poller = TelegramPoller(
        token="123456:fake_token",
        allowed_chats={22},
        allowed_users={33},
        enabled=True,
        request=lambda _method, _params: {
            "result": [
                {
                    "update_id": 7,
                    "message": {"message_id": 3, "chat": {"id": 22}, "from": {"id": 33}},
                }
            ]
        },
    )
    offsets = TelegramOffsetStore(tmp_path / "telegram-offset.json")
    result = poll_telegram_into_database(poller, session_factory=sessions, offset_store=offsets)
    assert result["offset"] == 8 and offsets.load() == 8
    with sessions() as session:
        from task_engine.models import EventInbox

        row = session.get(EventInbox, "telegram-update:7")
        assert row is not None and row.result["reason"] == "TEXT_REQUIRED"
    engine.dispose()


def test_telegram_edited_message_is_explicitly_ignored_and_replay_safe(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'telegram-edit.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    edited = {
        "update_id": 11,
        "edited_message": {
            "message_id": 5,
            "text": "Changed text",
            "chat": {"id": 22},
            "from": {"id": 33},
        },
    }
    poller = TelegramPoller(
        token="123456:fake_token",
        allowed_chats={22},
        allowed_users={33},
        enabled=True,
        request=lambda _method, _params: {"result": [edited]},
    )
    offsets = TelegramOffsetStore(tmp_path / "edit-offset.json")
    poll_telegram_into_database(poller, session_factory=sessions, offset_store=offsets)
    poll_telegram_into_database(poller, session_factory=sessions, offset_store=offsets)
    with sessions() as session:
        from task_engine.models import EventInbox

        assert session.query(EventInbox).count() == 1
        assert (
            session.get(EventInbox, "telegram-update:11").result["reason"]
            == "EDITED_MESSAGE_UNSUPPORTED"
        )
    engine.dispose()


def test_refinement_creates_history_and_approved_revision_is_immutable(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'requirements.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        demand = Demand(source="manual", external_id="refine-1", title="Bug", demand_type="bug")
        session.add(demand)
        session.flush()
        original = refine_requirement(
            session,
            demand,
            content="original spec",
            acceptance=["reproducible"],
            operator_comment="Initial refinement",
        )
        assert original.ears_clauses[0]["requires_clarification"] is True
        assert len(original.scenarios) == 2
        assert len(original.clarifications) == 1
        assert original.decision == "proposed"
        decide_revision(session, original, "approved")
        with pytest.raises(ValueError, match="APPROVED_REVISION_IMMUTABLE"):
            edit_revision(session, original, content="mutated", acceptance=["changed"])
        follow_up = refine_requirement(
            session,
            demand,
            content="QA follow-up",
            acceptance=["regression test"],
            operator_comment="Follow-up after approval",
        )
        assert original.content == "original spec"
        assert (original.version, follow_up.version) == (1, 2)
        assert len(follow_up.scenarios) == 2
    engine.dispose()
