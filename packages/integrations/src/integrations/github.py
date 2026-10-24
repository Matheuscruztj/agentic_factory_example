"""Read-only GitHub issues client with a fixed repository boundary."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(
        self,
        *,
        owner: str,
        repo: str,
        token: str,
        api_url: str = "https://api.github.com",
        request: Callable[[str, dict[str, str]], tuple[int, dict, dict[str, str]]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(
            r"[A-Za-z0-9_.-]+", repo
        ):
            raise GitHubError("INVALID_REPOSITORY")
        if not token:
            raise GitHubError("TOKEN_REQUIRED")
        if not api_url.startswith("https://"):
            raise GitHubError("TLS_REQUIRED")
        self.owner, self.repo, self.token = owner, repo, token
        self.api_url = api_url.rstrip("/")
        self._request = request or self._http
        self._sleep = sleep

    def _http(self, url: str, headers: dict[str, str]) -> tuple[int, dict, dict[str, str]]:
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=15) as response:
                return response.status, json.loads(response.read(2_000_000)), dict(response.headers)
        except HTTPError as exc:
            return exc.code, {}, dict(exc.headers)
        except (URLError, TimeoutError, OSError):
            raise GitHubError("NETWORK_ERROR") from None

    def get(self, path: str, *, params: dict[str, str] | None = None) -> dict | list:
        # Paths are relative API resource paths; repository is always pinned here.
        if path.startswith("/") or ".." in path or "?" in path or "#" in path:
            raise GitHubError("INVALID_API_PATH")
        url = f"{self.api_url}/repos/{self.owner}/{self.repo}/{path}"
        if params:
            url += "?" + urlencode(params)
        for attempt in range(4):
            status, body, headers = self._request(
                url,
                {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"},
            )
            if status == 200:
                return body
            if status == 429 or (status == 403 and headers.get("X-RateLimit-Remaining") == "0"):
                if attempt == 3:
                    raise GitHubError("RATE_LIMITED")
                delay = min(float(headers.get("Retry-After", 2**attempt)), 30.0)
                self._sleep(max(delay, 0.0))
                continue
            if status in {401, 403}:
                raise GitHubError("AUTH_OR_PERMISSION_DENIED")
            raise GitHubError(f"HTTP_{status}")
        raise GitHubError("RATE_LIMITED")

    def list_issues(
        self, *, page: int = 1, per_page: int = 100, since: str | None = None
    ) -> list[dict]:
        if not 1 <= page <= 10000 or not 1 <= per_page <= 100:
            raise GitHubError("INVALID_PAGE")
        params = {"state": "open", "page": str(page), "per_page": str(per_page)}
        if since:
            params["since"] = since
        rows = self.get("issues", params=params)
        if not isinstance(rows, list):
            raise GitHubError("INVALID_RESPONSE")
        return [row for row in rows if isinstance(row, dict) and "pull_request" not in row]

    def list_comments(self, issue_number: int, *, page: int = 1) -> list[dict]:
        if issue_number < 1:
            raise GitHubError("INVALID_ISSUE_NUMBER")
        rows = self.get(
            f"issues/{issue_number}/comments",
            params={"page": str(page), "per_page": "100"},
        )
        if not isinstance(rows, list):
            raise GitHubError("INVALID_RESPONSE")
        return rows
