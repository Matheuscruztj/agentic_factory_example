"""Opt-in, read-only Jira Cloud polling; never required by local workflows."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

import httpx


class JiraError(RuntimeError):
    pass


class JiraPoller:
    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str = "",
        email: str = "",
        token: str = "",
        project_key: str = "",
        request: Callable[[str, dict[str, Any]], tuple[int, dict[str, Any]]] | None = None,
    ) -> None:
        self.enabled = enabled
        self.base_url = base_url.rstrip("/")
        self.email, self.token, self.project_key = email, token, project_key
        self._request = request or self._http
        if enabled and (
            not re.fullmatch(r"https://[A-Za-z0-9.-]+\.atlassian\.net", self.base_url)
            or not email or not token or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,19}", project_key)
        ):
            raise JiraError("JIRA_CONFIGURATION_REQUIRED")

    @classmethod
    def from_env(cls, *, request=None) -> JiraPoller:
        return cls(
            enabled=os.getenv("JIRA_ENABLED", "false").casefold() == "true",
            base_url=os.getenv("JIRA_BASE_URL", ""),
            email=os.getenv("JIRA_EMAIL", ""),
            token=os.getenv("JIRA_API_TOKEN", ""),
            project_key=os.getenv("JIRA_PROJECT_KEY", ""),
            request=request,
        )

    def poll(self, *, start_at: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        if not 0 <= start_at <= 100_000 or not 1 <= limit <= 100:
            raise JiraError("JIRA_PAGE_INVALID")
        jql = f"project = {self.project_key} AND statusCategory != Done ORDER BY updated ASC"
        status, payload = self._request(
            "/rest/api/3/search/jql",
            {
                "jql": jql,
                "startAt": start_at,
                "maxResults": limit,
                "fields": ["summary", "description", "status", "updated", "labels"],
            },
        )
        if status == 401 or status == 403:
            raise JiraError("JIRA_AUTH_OR_PERMISSION_DENIED")
        if status != 200 or not isinstance(payload.get("issues"), list):
            raise JiraError("JIRA_POLL_FAILED")
        return [item for item in payload["issues"] if isinstance(item, dict)]

    def _http(self, path: str, params: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        try:
            response = httpx.get(
                self.base_url + path,
                params=params,
                auth=(self.email, self.token),
                headers={"Accept": "application/json"},
                timeout=15,
                follow_redirects=False,
                trust_env=False,
            )
            body = response.json()
            return response.status_code, body if isinstance(body, dict) else {}
        except (httpx.HTTPError, ValueError):
            raise JiraError("JIRA_NETWORK_OR_RESPONSE_ERROR") from None
