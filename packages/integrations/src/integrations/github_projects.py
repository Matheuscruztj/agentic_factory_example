"""Optional GitHub Projects v2 status mirror; local Task Engine is authoritative."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

import httpx


class ProjectsError(RuntimeError):
    pass


_NODE_ID = re.compile(r"^[A-Za-z0-9_=-]{1,200}$")
_MUTATION = """mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){
  updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}){
    projectV2Item{id}
  }
}"""


class GitHubProjectsMirror:
    def __init__(
        self,
        *,
        enabled: bool,
        token: str = "",
        project_id: str = "",
        request: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.enabled = enabled
        self._token = token
        self.project_id = project_id
        self._request = request or self._http
        if enabled and (not token or not _NODE_ID.fullmatch(project_id)):
            raise ProjectsError("PROJECT_CONFIGURATION_REQUIRED")

    @classmethod
    def from_env(cls, *, request=None) -> GitHubProjectsMirror:
        enabled = os.getenv("GITHUB_PROJECTS_ENABLED", "false").casefold() == "true"
        return cls(
            enabled=enabled,
            token=os.getenv("GITHUB_TOKEN", ""),
            project_id=os.getenv("GITHUB_PROJECT_V2_ID", ""),
            request=request,
        )

    def sync_status(self, *, item_id: str, field_id: str, option_id: str) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "disabled", "local_task_engine_affected": False}
        if any(not _NODE_ID.fullmatch(value) for value in (item_id, field_id, option_id)):
            raise ProjectsError("PROJECT_NODE_ID_INVALID")
        result = self._request(
            _MUTATION,
            {
                "project": self.project_id,
                "item": item_id,
                "field": field_id,
                "option": option_id,
                "token": self._token,
            },
        )
        if result.get("errors"):
            raise ProjectsError("PROJECT_GRAPHQL_REJECTED")
        item = result.get("data", {}).get("updateProjectV2ItemFieldValue", {}).get("projectV2Item")
        if not isinstance(item, dict) or item.get("id") != item_id:
            raise ProjectsError("PROJECT_RESPONSE_INVALID")
        return {"status": "synced", "item_id": item_id}

    @staticmethod
    def _http(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        token = variables.pop("token")
        try:
            response = httpx.post(
                "https://api.github.com/graphql",
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=15,
                follow_redirects=False,
                trust_env=False,
            )
            if response.status_code != 200:
                raise ProjectsError("PROJECT_HTTP_ERROR")
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        except (httpx.HTTPError, ValueError):
            raise ProjectsError("PROJECT_NETWORK_OR_RESPONSE_ERROR") from None
