"""Restart-safe polling orchestration around the read-only GitHub client."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta


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
    cursor = load_cursor()
    since = (cursor - overlap).isoformat().replace("+00:00", "Z") if cursor else None
    imported = 0
    pages = 0
    latest = cursor or now
    for page in range(1, max_pages + 1):
        rows = client.list_issues(page=page, since=since)
        pages += 1
        for issue in rows:
            import_issue(issue)
            updated = issue.get("updated_at")
            if isinstance(updated, str):
                try:
                    parsed = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    if parsed > latest:
                        latest = parsed
                except ValueError:
                    pass
            imported += 1
        if len(rows) < 100:
            break
    else:
        raise RuntimeError("POLL_PAGE_LIMIT_REACHED_CURSOR_NOT_ADVANCED")
    save_cursor(min(latest, now))
    return {"status": "pass", "pages": pages, "imported": imported}
