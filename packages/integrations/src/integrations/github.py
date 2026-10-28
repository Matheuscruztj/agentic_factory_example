"""Read-only GitHub issues client with a fixed repository boundary."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import urlencode, urlsplit

import httpx


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(
        self,
        *,
        owner: str,
        repo: str,
        token: str = "",
        token_provider: Callable[[], str] | None = None,
        api_url: str = "https://api.github.com",
        request: Callable[[str, dict[str, str]], tuple[int, dict, dict[str, str]]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(
            r"[A-Za-z0-9_.-]+", repo
        ):
            raise GitHubError("INVALID_REPOSITORY")
        if not token and token_provider is None:
            raise GitHubError("TOKEN_REQUIRED")
        parsed_api = urlsplit(api_url)
        if (
            parsed_api.scheme != "https"
            or not parsed_api.hostname
            or parsed_api.username
            or parsed_api.password
            or parsed_api.query
            or parsed_api.fragment
            or ".." in parsed_api.path.split("/")
        ):
            raise GitHubError("INVALID_API_BASE_URL")
        self.owner, self.repo = owner, repo
        self._token_provider = token_provider or (lambda: token)
        self.api_url = api_url.rstrip("/")
        self._request = request or self._http
        self._sleep = sleep

    def _http(self, url: str, headers: dict[str, str]) -> tuple[int, dict, dict[str, str]]:
        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=15,
                follow_redirects=False,
                trust_env=False,
            )
        except httpx.HTTPError:
            raise GitHubError("NETWORK_ERROR") from None
        try:
            body = response.json()
        except (ValueError, UnicodeDecodeError):
            body = {}
        if not isinstance(body, (dict, list)):
            raise GitHubError("INVALID_RESPONSE") from None
        return response.status_code, body, {
            key.lower(): value for key, value in response.headers.items()
        }

    def get(self, path: str, *, params: dict[str, str] | None = None) -> dict | list:
        return self.get_with_headers(path, params=params)[0]

    def get_with_headers(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> tuple[dict | list, dict[str, str]]:
        # Paths are relative API resource paths; repository is always pinned here.
        if path not in {"", "repository", "issues"} and not re.fullmatch(
            r"issues/[1-9][0-9]*(?:/comments)?", path
        ):
            raise GitHubError("INVALID_API_PATH")
        suffix = "" if path in {"", "repository"} else f"/{path}"
        url = f"{self.api_url}/repos/{self.owner}/{self.repo}{suffix}"
        if params:
            url += "?" + urlencode(params)
        for attempt in range(4):
            token = self._token_provider()
            if not token:
                raise GitHubError("TOKEN_REQUIRED")
            status, body, headers = self._request(
                url,
                {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            )
            headers = {str(key).lower(): str(value) for key, value in headers.items()}
            if status == 200:
                return body, headers
            if status == 429 or (
                status == 403
                and (headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers)
            ):
                if attempt == 3:
                    raise GitHubError("RATE_LIMITED")
                try:
                    delay = float(headers.get("retry-after", 2**attempt))
                except (TypeError, ValueError):
                    delay = float(2**attempt)
                delay = min(delay, 30.0)
                self._sleep(max(delay, 0.0))
                continue
            if status in {401, 403}:
                raise GitHubError("AUTH_OR_PERMISSION_DENIED")
            raise GitHubError(f"HTTP_{status}")
        raise GitHubError("RATE_LIMITED")

    def verify_repository_access(self) -> dict[str, str | bool]:
        """Prove the configured credential can read exactly the pinned repository."""
        repository = self.get("repository")
        if not isinstance(repository, dict):
            raise GitHubError("INVALID_REPOSITORY_RESPONSE")
        full_name = repository.get("full_name")
        expected = f"{self.owner}/{self.repo}"
        if not isinstance(full_name, str) or full_name.casefold() != expected.casefold():
            raise GitHubError("REPOSITORY_IDENTITY_MISMATCH")
        return {
            "repository": expected,
            "private": bool(repository.get("private", False)),
            "read_access": True,
        }

    def list_issues(
        self, *, page: int = 1, per_page: int = 100, since: str | None = None
    ) -> list[dict]:
        rows, _, _ = self.list_issue_page(page=page, per_page=per_page, since=since)
        return [row for row in rows if "pull_request" not in row]

    def list_issue_page(
        self, *, page: int = 1, per_page: int = 100, since: str | None = None
    ) -> tuple[list[dict], int, bool | None]:
        if not 1 <= page <= 10000 or not 1 <= per_page <= 100:
            raise GitHubError("INVALID_PAGE")
        # Poll all states so closed/reopened updates remain visible during overlap.
        params = {"state": "all", "page": str(page), "per_page": str(per_page)}
        if since:
            params["since"] = since
        rows, headers = self.get_with_headers("issues", params=params)
        if not isinstance(rows, list):
            raise GitHubError("INVALID_RESPONSE")
        raw_count = len(rows)
        link_header = headers.get("link", "")
        has_next = (
            bool(re.search(r'<[^>]+>\s*;\s*rel="?next"?', link_header)) if link_header else None
        )
        return [row for row in rows if isinstance(row, dict)], raw_count, has_next

    def list_comments(self, issue_number: int, *, page: int = 1) -> list[dict]:
        if issue_number < 1:
            raise GitHubError("INVALID_ISSUE_NUMBER")
        if not 1 <= page <= 10000:
            raise GitHubError("INVALID_PAGE")
        rows = self.get(
            f"issues/{issue_number}/comments",
            params={"page": str(page), "per_page": "100"},
        )
        if not isinstance(rows, list):
            raise GitHubError("INVALID_RESPONSE")
        return rows
