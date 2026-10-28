from datetime import UTC, datetime, timedelta

from factory_workers.github_poll import poll_github
from factory_workers.telegram_offset import TelegramOffsetStore
from factory_workers.telegram_poll import poll_telegram_into_database
from integrations.github import GitHubClient
from integrations.provider_simulator import FakeClock, LocalProviderSimulator, ProviderFault
from integrations.telegram import TelegramNotifier, TelegramPoller
from shared_contracts.db import Base
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import Demand


def test_github_transport_and_worker_use_paginated_issue_history(tmp_path):
    simulator = LocalProviderSimulator(page_size=2)
    simulator.issues = [
        {"number": 1, "title": "one", "body": "body", "updated_at": "2026-01-01T00:00:00Z"},
        {"number": 2, "title": "pr", "pull_request": {}, "updated_at": "2026-01-01T00:00:00Z"},
        {"number": 3, "title": "three", "body": "body", "updated_at": "2026-01-01T00:01:00Z"},
    ]
    client = GitHubClient(
        owner=simulator.owner, repo=simulator.repo, token="test", request=simulator.github_request
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'simulated-github.db'}")
    Base.metadata.create_all(engine)
    imported = []
    result = poll_github(
        client,
        load_cursor=lambda: None,
        save_cursor=lambda cursor: imported.append(("cursor", cursor)),
        import_issue=lambda issue: imported.append(("issue", issue["number"])),
        now=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
    )
    assert result["pages"] == 2
    assert result["imported"] == 2
    assert [item[1] for item in imported if item[0] == "issue"] == [1, 3]
    assert [row["boundary"] for row in simulator.journal] == [
        "github:issues:page:1",
        "github:issues:page:2",
    ]
    assert simulator.fidelity["provider_certification"] is False
    engine.dispose()


def test_telegram_worker_journals_and_deduplicates_updates_with_simulator(tmp_path):
    simulator = LocalProviderSimulator(clock=FakeClock(datetime(2026, 1, 1, tzinfo=UTC)))
    simulator.telegram_updates.append(
        {
            "update_id": 9,
            "message": {
                "message_id": 3,
                "text": "Please inspect a local regression",
                "chat": {"id": 22},
                "from": {"id": 33, "username": "tester"},
            },
        }
    )
    poller = TelegramPoller(
        token="123:fake-token",
        allowed_chats={22},
        allowed_users={33},
        enabled=True,
        request=lambda method, params: simulator.telegram_request(method, params),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'simulated-telegram.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    offsets = TelegramOffsetStore(tmp_path / "offset.json")
    result = poll_telegram_into_database(poller, session_factory=sessions, offset_store=offsets)
    replay = poll_telegram_into_database(poller, session_factory=sessions, offset_store=offsets)
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(Demand)) == 1
    assert result["offset"] == 10 and offsets.load() == 10
    assert replay["offset"] == 10 and replay["imported"] == 0
    assert simulator.journal[0]["boundary"] == "telegram:getUpdates"
    engine.dispose()


def test_simulator_injects_one_shot_fault_and_records_outbound_replies():
    simulator = LocalProviderSimulator()
    simulator.fail_once(ProviderFault("telegram:sendMessage", status=429))
    notifier = TelegramNotifier(
        token="123:fake-token", allowed_chats={77}, enabled=True, request=simulator.telegram_request
    )
    try:
        notifier.send_message(chat_id=77, text="first", reply_to_message_id=4)
    except Exception as exc:
        assert "RATE_LIMITED" in str(exc)
    else:
        raise AssertionError("injected 429 should be visible to the real transport")
    result = notifier.send_message(chat_id=77, text="second", reply_to_message_id=4)
    assert result["message_id"] == 1
    assert simulator.telegram_messages[0]["text"] == "second"
    assert simulator.telegram_messages[0]["reply_to_message_id"] == 4
    assert [entry["boundary"] for entry in simulator.journal] == [
        "telegram:sendMessage",
        "telegram:sendMessage",
    ]
    assert simulator.clock.advance(timedelta(seconds=2)) == datetime(
        2026, 1, 1, 0, 0, 2, tzinfo=UTC
    )
