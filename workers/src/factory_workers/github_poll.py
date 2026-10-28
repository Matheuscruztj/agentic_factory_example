"""Restart-safe polling orchestration around the read-only GitHub client."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from task_engine.intake import IntakeError, normalize_intake, reconcile_intake
from task_engine.models import EventInbox

from factory_workers.github_cursor import JsonCursorStore


def _normalized_labels(issue: dict[str, Any]) -> list[str]:
    raw_labels = issue.get("labels")
    if not isinstance(raw_labels, list):
        return []
    labels: list[str] = []
    for label in raw_labels:
        if not isinstance(label, dict):
            continue
        name = label.get("name")
        if isinstance(name, str):
            labels.append(name[:100])
        if len(labels) == 50:
            break
    return labels


def poll_github_comments_into_database(
    client: Any,
    *,
    session_factory: Callable[[], Any],
    demand_id: str,
    issue_number: int,
    max_pages: int = 20,
) -> dict[str, int | str]:
    """Persist comment edits as immutable, redacted events linked to their demand."""
    if not demand_id or type(issue_number) is not int or issue_number < 1 or max_pages < 1:
        raise ValueError("GITHUB_COMMENT_POLL_ARGUMENT_INVALID")
    from context_engine.pack import build_context_pack

    imported = pages = 0
    for page in range(1, max_pages + 1):
        comments = client.list_comments(issue_number, page=page)
        if not isinstance(comments, list):
            raise ValueError("GITHUB_COMMENT_PAGE_INVALID")
        pages += 1
        for comment in comments:
            if not isinstance(comment, dict) or type(comment.get("id")) is not int:
                continue
            raw_user = comment.get("user")
            user = raw_user if isinstance(raw_user, dict) else {}
            updated_at = comment.get("updated_at") or comment.get("created_at") or "unknown"
            if not isinstance(updated_at, str):
                updated_at = "unknown"
            version_key = (
                f"{client.owner}/{client.repo}#{issue_number}:comment:{comment['id']}:{updated_at}"
            )
            event_id = "github-comment:" + hashlib.sha256(version_key.encode()).hexdigest()
            comment_text = str(comment.get("body", ""))[:20_000]
            safe = build_context_pack(
                task={"id": demand_id, "title": "GitHub comment"},
                snippets=[{
                    "path": "github/comment.txt",
                    "blob_sha": hashlib.sha256(comment_text.encode()).hexdigest(),
                    "text": comment_text,
                }],
                allowed_paths={"github/comment.txt"},
                max_tokens=6000,
            )
            body = safe.content["L2"][0]["text"] if safe.content["L2"] else ""
            snapshot = {
                "demand_id": demand_id,
                "repository": f"{client.owner}/{client.repo}",
                "issue_number": issue_number,
                "comment_id": comment["id"],
                "version_key": version_key,
                "author": str(user.get("login", "unknown"))[:160],
                "body": body,
                "approval_state": "proposal_only",
            }
            with session_factory() as session:
                try:
                    if session.get(EventInbox, event_id) is None:
                        session.add(EventInbox(event_id=event_id, result=snapshot))
                        session.commit()
                        imported += 1
                except Exception:
                    session.rollback()
                    raise
        if len(comments) < 100:
            break
    else:
        raise RuntimeError("GITHUB_COMMENT_PAGE_LIMIT_REACHED")
    return {"status": "pass", "pages": pages, "imported": imported}


def poll_github(
    client,
    *,
    load_cursor: Callable[[], datetime | None],
    save_cursor: Callable[[datetime], None],
    import_issue: Callable[[dict], None],
    now: datetime,
    overlap: timedelta = timedelta(minutes=5),
    max_pages: int = 20,
) -> dict[str, int | str]:
    """Import open issues and advance watermark only after every page succeeds."""
    if overlap < timedelta(0) or max_pages < 1:
        raise ValueError("INVALID_POLL_CONFIGURATION")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("POLL_TIME_MUST_BE_TIMEZONE_AWARE")
    now = now.astimezone(UTC)
    cursor = load_cursor()
    if cursor is not None:
        if cursor.tzinfo is None or cursor.utcoffset() is None:
            raise ValueError("POLL_CURSOR_MUST_BE_TIMEZONE_AWARE")
        cursor = cursor.astimezone(UTC)
    since = (cursor - overlap).isoformat().replace("+00:00", "Z") if cursor else None
    imported = 0
    pages = 0
    latest = cursor or now
    for page in range(1, max_pages + 1):
        raw_count = None
        has_next = None
        if hasattr(client, "list_issue_page"):
            rows, raw_count, has_next = client.list_issue_page(page=page, since=since)
        else:
            rows = client.list_issues(page=page, since=since)
        pages += 1
        for issue in rows:
            updated = issue.get("updated_at")
            if isinstance(updated, str):
                try:
                    parsed = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
                        parsed = parsed.astimezone(UTC)
                    else:
                        parsed = latest
                    if parsed > latest:
                        latest = parsed
                except ValueError:
                    pass
            if "pull_request" in issue:
                continue
            import_issue(issue)
            imported += 1
        if has_next is False or (has_next is None and (raw_count or len(rows)) < 100):
            break
    else:
        raise RuntimeError("POLL_PAGE_LIMIT_REACHED_CURSOR_NOT_ADVANCED")
    save_cursor(min(latest, now))
    return {"status": "pass", "pages": pages, "imported": imported}


def poll_github_persisted(
    client,
    *,
    cursor_store: JsonCursorStore,
    import_issue: Callable[[dict], None],
    now: datetime,
    overlap: timedelta = timedelta(minutes=5),
    max_pages: int = 20,
) -> dict[str, int | str]:
    """Production entry point using an atomic local cursor that survives restart."""
    return poll_github(
        client,
        load_cursor=cursor_store.load,
        save_cursor=cursor_store.save,
        import_issue=import_issue,
        now=now,
        overlap=overlap,
        max_pages=max_pages,
    )


def poll_github_into_database(
    client: Any,
    *,
    session_factory: Callable[[], Any],
    cursor_store: JsonCursorStore,
    now: datetime,
    overlap: timedelta = timedelta(minutes=5),
    max_pages: int = 20,
) -> dict[str, int | str]:
    """Poll the fixed GitHub repository and idempotently store normalized issues."""

    def import_issue(issue: dict) -> None:
        number = issue.get("number")
        if type(number) is not int or number < 1:
            raise ValueError("GITHUB_ISSUE_NUMBER_INVALID")
        raw_user = issue.get("user")
        user = cast(dict[str, object], raw_user) if isinstance(raw_user, dict) else {}
        try:
            message = normalize_intake(
                {
                    "source": "github",
                    "external_id": f"{client.owner}/{client.repo}#{number}",
                    "url": issue.get("html_url"),
                    "author": user.get("login") or "unknown",
                    "title": issue.get("title", ""),
                    "text": issue.get("body") or issue.get("title", ""),
                    "demand_type": "bug"
                    if any(
                        isinstance(label, dict) and str(label.get("name", "")).lower() == "bug"
                        for label in issue.get("labels", [])
                    )
                    else "question",
                }
            )
        except IntakeError as exc:
            raise ValueError("GITHUB_ISSUE_INVALID") from exc
        with session_factory() as session:
            try:
                demand, created = reconcile_intake(session, message)
                updated_at = issue.get("updated_at")
                if not isinstance(updated_at, str) or not updated_at.strip():
                    updated_at = "unknown"
                version_key = f"{client.owner}/{client.repo}#{number}:{updated_at}"
                event_id = "github-snapshot:" + hashlib.sha256(version_key.encode()).hexdigest()
                snapshot = {
                    "demand_id": demand.id,
                    "repository": f"{client.owner}/{client.repo}",
                    "issue_number": number,
                    "state": (
                        issue.get("state")
                        if issue.get("state") in {"open", "closed"}
                        else "unknown"
                    ),
                    "updated_at": updated_at,
                    "version_key": version_key,
                    "title": message.title,
                    "author": message.author,
                    "source_url": message.url,
                    "created": created,
                    "labels": _normalized_labels(issue),
                }
                if session.get(EventInbox, event_id) is None:
                    session.add(EventInbox(event_id=event_id, result=snapshot))
                session.commit()
            except Exception:
                session.rollback()
                raise

    return poll_github_persisted(
        client,
        cursor_store=cursor_store,
        import_issue=import_issue,
        now=now,
        overlap=overlap,
        max_pages=max_pages,
    )
