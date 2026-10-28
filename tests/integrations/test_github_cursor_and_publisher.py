from datetime import UTC, datetime

import pytest
from factory_workers.github_cursor import JsonCursorStore
from factory_workers.github_poll import (
    poll_github,
    poll_github_comments_into_database,
    poll_github_into_database,
)
from integrations.github_publisher import PublicationApproval, publish_pull_request
from integrations.telegram import TelegramError, TelegramNotifier
from shared_contracts.db import Base
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import Demand, EventInbox


def test_cursor_store_survives_restart_and_is_timezone_normalized(tmp_path):
    path = tmp_path / "cursor.json"
    first = JsonCursorStore(path)
    cursor = datetime(2026, 10, 24, 12, tzinfo=UTC)
    first.save(cursor)
    assert JsonCursorStore(path).load() == cursor
    assert path.stat().st_mode & 0o777 == 0o600


def test_cursor_store_rejects_malformed_cursor(tmp_path):
    path = tmp_path / "cursor.json"
    path.write_text('{"schema":1,"updated_at":"yesterday"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="GITHUB_CURSOR_INVALID"):
        JsonCursorStore(path).load()


def test_github_poll_persists_cursor_and_reconciles_replay(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'intake.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    class FakeGitHub:
        owner = "org"
        repo = "repo"

        def list_issues(self, *, page, since):
            if page > 1:
                return []
            return [{
                "number": 42,
                "title": "Synthetic issue",
                "body": "Synthetic body",
                "updated_at": "2026-10-24T12:00:00Z",
                "html_url": "https://github.com/org/repo/issues/42",
                "user": {"login": "synthetic"},
                "labels": [],
            }]

    store = JsonCursorStore(tmp_path / "cursor.json")
    now = datetime(2026, 10, 24, 12, 5, tzinfo=UTC)
    first = poll_github_into_database(
        FakeGitHub(), session_factory=factory, cursor_store=store, now=now
    )
    reopened = poll_github_into_database(
        FakeGitHub(), session_factory=factory,
        cursor_store=JsonCursorStore(tmp_path / "cursor.json"), now=now,
    )
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(Demand))
    assert first["imported"] == 1 and reopened["imported"] == 1
    assert count == 1
    assert store.load() == now
    engine.dispose()


def test_pull_request_in_full_page_does_not_truncate_issue_pagination():
    class PaginatedGitHub:
        owner = "org"
        repo = "repo"

        def __init__(self):
            self.pages = []

        def list_issue_page(self, *, page, since):
            self.pages.append((page, since))
            if page == 1:
                rows = [{"number": n, "updated_at": "2026-10-24T12:00:00Z"} for n in range(1, 100)]
                rows.append({"number": 100, "pull_request": {"url": "ignored"}})
                return rows, 100, True
            return [{"number": 101, "updated_at": "2026-10-24T12:01:00Z"}], 1, False

    client = PaginatedGitHub()
    imported = []
    saved = []
    now = datetime(2026, 10, 24, 12, 5, tzinfo=UTC)
    result = poll_github(
        client,
        load_cursor=lambda: None,
        save_cursor=saved.append,
        import_issue=imported.append,
        now=now,
    )
    assert result["pages"] == 2
    assert result["imported"] == 100
    assert [page for page, _ in client.pages] == [1, 2]
    assert saved == [now]


def test_github_issue_state_changes_are_versioned_without_mutating_demand_state(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'issue-history.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    class FakeGitHub:
        owner = "org"
        repo = "repo"
        state = "open"
        updated_at = "2026-10-24T12:00:00Z"

        def list_issue_page(self, *, page, since):
            if page > 1:
                return [], 0, False
            return ([{
                "number": 7, "title": "Issue", "body": "Body", "state": self.state,
                "updated_at": self.updated_at,
                "html_url": "https://github.com/org/repo/issues/7",
                "user": {"login": "tester"}, "labels": [],
            }], 1, False)

    client = FakeGitHub()
    cursor = JsonCursorStore(tmp_path / "history-cursor.json")
    poll_github_into_database(
        client, session_factory=factory, cursor_store=cursor,
        now=datetime(2026, 10, 24, 12, 5, tzinfo=UTC),
    )
    client.state = "closed"
    client.updated_at = "2026-10-24T12:10:00Z"
    poll_github_into_database(
        client, session_factory=factory, cursor_store=cursor,
        now=datetime(2026, 10, 24, 12, 15, tzinfo=UTC),
    )
    with factory() as session:
        demand = session.scalars(select(Demand)).one()
        snapshots = session.scalars(
            select(EventInbox).where(EventInbox.event_id.like("github-snapshot:%"))
        ).all()
    assert demand.status == "new"
    assert {row.result["state"] for row in snapshots} == {"open", "closed"}
    assert len(snapshots) == 2
    engine.dispose()


def test_github_comment_edits_are_versioned_redacted_and_proposal_only(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'comments.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    class FakeGitHub:
        owner = "org"
        repo = "repo"
        comments = [{
            "id": 12,
            "created_at": "2026-10-24T12:00:00Z",
            "updated_at": "2026-10-24T12:00:00Z",
            "body": "Please inspect token=secret-value",
            "user": {"login": "reporter"},
        }]

        def list_comments(self, issue_number, *, page):
            return self.comments if page == 1 else []

    client = FakeGitHub()
    first = poll_github_comments_into_database(
        client, session_factory=factory, demand_id="demand-1", issue_number=7
    )
    client.comments = [{
        **client.comments[0], "updated_at": "2026-10-24T12:05:00Z", "body": "Clarified response",
    }]
    second = poll_github_comments_into_database(
        client, session_factory=factory, demand_id="demand-1", issue_number=7
    )
    with factory() as session:
        rows = session.scalars(
            select(EventInbox).where(EventInbox.event_id.like("github-comment:%"))
        ).all()
    assert first["imported"] == second["imported"] == 1
    assert len(rows) == 2
    assert all(row.result["approval_state"] == "proposal_only" for row in rows)
    assert "secret-value" not in str(rows)
    engine.dispose()


def test_publisher_requires_separate_repo_and_sha_bound_approvals():
    class FakeTransport:
        calls = []
        branch = None
        pull_request = None

        def branch_sha(self, repository, branch):
            self.calls.append(("branch", repository, branch))
            return self.branch

        def find_pull_request(self, repository, branch, commit_sha):
            self.calls.append(("find_pr", repository, branch, commit_sha))
            return self.pull_request

        def push_branch(self, repository, branch, commit_sha):
            self.calls.append(("push", repository, branch, commit_sha))
            self.branch = commit_sha
            return commit_sha

        def create_pull_request(self, repository, branch, title, body):
            self.calls.append(("pr", repository, branch, title, body))
            self.pull_request = "https://github.invalid/org/repo/pull/1"
            return self.pull_request

    transport = FakeTransport()
    sha = "a" * 40
    push = PublicationApproval("push", "org/repo", sha, "approved", "operator")
    pr = PublicationApproval("create_pr", "org/repo", sha, "approved", "operator")
    with pytest.raises(PermissionError, match="PUSH_APPROVAL_REQUIRED"):
        publish_pull_request(
            transport, repository="org/repo", allowed_repository="org/repo",
            branch="agent/task", commit_sha=sha, title="Update", evidence_body="checks pass",
            push_approval=None, pr_approval=pr, redact=lambda value: value,
        )
    result = publish_pull_request(
        transport, repository="org/repo", allowed_repository="org/repo",
        branch="agent/task", commit_sha=sha, title="Update", evidence_body="checks pass",
        push_approval=push, pr_approval=pr,
        redact=lambda value: value.replace("secret", "[redacted]"),
    )
    assert result["commit_sha"] == sha
    assert [call[0] for call in transport.calls] == ["branch", "push", "find_pr", "pr"]
    repeated = publish_pull_request(
        transport, repository="org/repo", allowed_repository="org/repo",
        branch="agent/task", commit_sha=sha, title="Update", evidence_body="checks pass",
        push_approval=push, pr_approval=pr, redact=lambda value: value,
    )
    assert repeated == result
    assert [call[0] for call in transport.calls].count("push") == 1
    assert [call[0] for call in transport.calls].count("pr") == 1


def test_telegram_notifier_is_allowlisted_bounded_and_redacts_sensitive_text():
    calls = []

    def request(method, params):
        calls.append((method, params))
        return {"ok": True, "result": {"message_id": 9}}

    notifier = TelegramNotifier(
        token="123:fake-token", allowed_chats={77}, enabled=True, request=request,
        max_length=80,
    )
    result = notifier.send_message(
        chat_id=77,
        text="token=topsecret contact alice@example.com progress " + "x" * 100,
        reply_to_message_id=4,
    )
    assert result == {"chat_id": 77, "message_id": 9, "redacted": True}
    assert calls[0][0] == "sendMessage"
    assert calls[0][1]["reply_to_message_id"] == 4
    assert len(calls[0][1]["text"]) == 80
    assert "topsecret" not in calls[0][1]["text"]
    assert "alice@example.com" not in calls[0][1]["text"]
    with pytest.raises(TelegramError, match="CHAT_NOT_ALLOWED"):
        notifier.send_message(chat_id=78, text="private")
