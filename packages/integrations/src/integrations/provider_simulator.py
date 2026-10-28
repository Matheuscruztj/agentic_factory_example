"""Deterministic, local-only subsets of the GitHub and Telegram APIs.

These simulators are contract aids for transport/worker tests. They deliberately
do not open sockets, persist credentials, or claim provider certification.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit


@dataclass
class FakeClock:
    """Controllable UTC clock for repeatable cursor and retry tests."""

    value: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=UTC))

    def __post_init__(self) -> None:
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValueError("SIMULATOR_CLOCK_MUST_BE_AWARE")
        self.value = self.value.astimezone(UTC)

    def now(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> datetime:
        if delta < timedelta(0):
            raise ValueError("SIMULATOR_CLOCK_CANNOT_REWIND")
        self.value += delta
        return self.value


@dataclass
class ProviderFault:
    """One-shot failure injected at a named request boundary."""

    boundary: str
    status: int = 503
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = field(default_factory=dict)


class LocalProviderSimulator:
    """Small stateful fake implementing only the integration paths in use."""

    fidelity = {
        "schema": 1,
        "status": "local_contract_simulator",
        "supports": [
            "github_issue_comment_pagination_and_edits",
            "github_issue_pull_request_filtering",
            "telegram_updates_and_edits",
            "telegram_replies_and_sends",
            "request_journal_and_one_shot_faults",
            "controllable_clock",
        ],
        "does_not_model": ["provider_rate_policy", "oauth", "network_tls", "live_webhooks"],
        "provider_certification": False,
    }

    def __init__(
        self,
        *,
        owner: str = "example",
        repo: str = "factory-test",
        page_size: int = 100,
        clock: FakeClock | None = None,
    ) -> None:
        if page_size < 1 or page_size > 100:
            raise ValueError("SIMULATOR_PAGE_SIZE_INVALID")
        self.owner, self.repo = owner, repo
        self.page_size = page_size
        self.clock = clock or FakeClock()
        self.issues: list[dict[str, Any]] = []
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.telegram_updates: deque[dict[str, Any]] = deque()
        self.telegram_messages: list[dict[str, Any]] = []
        self.journal: list[dict[str, Any]] = []
        self.faults: deque[ProviderFault] = deque()
        self._next_message_id = 1

    def fail_once(self, fault: ProviderFault) -> None:
        self.faults.append(fault)

    def _fault(self, boundary: str) -> tuple[int, Any, dict[str, str]] | None:
        if self.faults and self.faults[0].boundary == boundary:
            fault = self.faults.popleft()
            self.journal.append(
                {"boundary": boundary, "status": fault.status, "at": self.clock.now().isoformat()}
            )
            return fault.status, fault.body, fault.headers
        return None

    def github_request(self, url: str, headers: dict[str, str]) -> tuple[int, Any, dict[str, str]]:
        parsed = urlsplit(url)
        prefix = f"/repos/{self.owner}/{self.repo}"
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.github.com"
            or not parsed.path.startswith(prefix)
        ):
            return 404, {}, {}
        resource = parsed.path[len(prefix) :].strip("/")
        query = parse_qs(parsed.query)
        boundary = f"github:{resource or 'repository'}:page:{query.get('page', ['1'])[0]}"
        injected = self._fault(boundary)
        if injected:
            return injected
        self.journal.append(
            {
                "boundary": boundary,
                "at": self.clock.now().isoformat(),
                "authorization_present": bool(headers.get("Authorization")),
            }
        )
        if resource == "" and not query:
            return 200, {"full_name": f"{self.owner}/{self.repo}", "private": True}, {}
        if resource == "issues":
            page = int(query.get("page", ["1"])[0])
            start = (page - 1) * self.page_size
            rows = self.issues[start : start + self.page_size]
            has_next = start + self.page_size < len(self.issues)
            link = (
                f"<https://api.github.com/repos/{self.owner}/{self.repo}/issues?page="
                f'{page + 1}>; rel="next"'
                if has_next
                else ""
            )
            return 200, rows, ({"link": link} if link else {})
        if resource.startswith("issues/") and resource.endswith("/comments"):
            parts = resource.split("/")
            issue_number = int(parts[1])
            page = int(query.get("page", ["1"])[0])
            rows = self.comments.get(issue_number, [])
            start = (page - 1) * self.page_size
            return 200, rows[start : start + self.page_size], {}
        return 404, {}, {}

    def telegram_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        boundary = f"telegram:{method}"
        injected = self._fault(boundary)
        if injected:
            status, body, _headers = injected
            if status == 429:
                return {"ok": False, "error_code": 429, "description": str(body)}
            return {"ok": False, "error_code": status, "description": str(body)}
        self.journal.append({"boundary": boundary, "at": self.clock.now().isoformat()})
        if method == "getUpdates":
            offset = int(params.get("offset", 0))
            updates = [
                item for item in self.telegram_updates if int(item.get("update_id", -1)) >= offset
            ]
            timeout = int(params.get("timeout", 0))
            return {"ok": True, "result": updates[:100], "simulated_timeout": timeout}
        if method == "sendMessage":
            message = {
                **params,
                "message_id": self._next_message_id,
                "date": int(self.clock.now().timestamp()),
            }
            self._next_message_id += 1
            self.telegram_messages.append(message)
            return {"ok": True, "result": message}
        return {"ok": False, "error_code": 404}
