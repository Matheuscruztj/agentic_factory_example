"""Server-side allowlisted conversation tools; no shell, writes, or arbitrary HTTP."""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable

from context_engine.pack import build_context_pack

from agent_runtime.intent_router import TaskProposal


class ToolDenied(PermissionError):
    pass


_TOOLS_BY_PERSONA = {
    "analyst": frozenset({"get_issue_context", "search_allowed_code", "propose_task"}),
    "qa": frozenset(
        {"get_issue_context", "get_task_status", "search_allowed_code", "propose_task"}
    ),
    "backend": frozenset(
        {"get_issue_context", "get_task_status", "search_allowed_code", "propose_task"}
    ),
    "frontend": frozenset(
        {"get_issue_context", "get_task_status", "search_allowed_code", "propose_task"}
    ),
    "reviewer": frozenset(
        {"get_issue_context", "get_task_status", "search_allowed_code", "read_artifact"}
    ),
}


class ToolGateway:
    def __init__(
        self,
        *,
        load_binding: Callable[[str], dict | None],
        path_policy: Callable[[dict], set[str]],
        issue_context: Callable[[str], dict],
        task_status: Callable[[str], dict],
        search_code: Callable[[str, set[str]], list[dict]],
        store_proposal: Callable[[dict, TaskProposal], dict],
        read_authorized_artifact: Callable[[dict, str, int, int], dict] | None = None,
        max_calls: int = 30,
        window_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if type(max_calls) is not int or max_calls < 1 or window_seconds < 1:
            raise ValueError("INVALID_TOOL_QUOTA")
        self._load_binding = load_binding
        self._path_policy = path_policy
        self._issue_context = issue_context
        self._task_status = task_status
        self._search_code = search_code
        self._store_proposal = store_proposal
        self._read_authorized_artifact = read_authorized_artifact
        self._max_calls = max_calls
        self._window = window_seconds
        self._clock = clock
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def invoke(self, *, actor: str, binding_id: str, tool: str, arguments: dict) -> dict:
        if not actor.strip():
            raise ToolDenied("ACTOR_REQUIRED")
        if not isinstance(arguments, dict):
            raise ValueError("INVALID_TOOL_ARGUMENTS")
        binding = self._load_binding(binding_id)
        if binding is None:
            raise ToolDenied("THREAD_BINDING_REQUIRED")
        allowed = _TOOLS_BY_PERSONA.get(binding.get("persona"), frozenset())
        if tool not in allowed:
            raise ToolDenied("TOOL_NOT_ALLOWED")
        self._consume_quota(actor)
        if tool == "get_issue_context":
            result = self._issue_context(binding["entity_id"])
            return {"context": self._sanitize(binding, result)}
        if tool == "get_task_status":
            if binding.get("entity_type") != "task":
                raise ToolDenied("TASK_TOOL_REQUIRES_TASK_BINDING")
            return {"task": self._sanitize(binding, self._task_status(binding["entity_id"]))}
        if tool == "search_allowed_code":
            query = arguments.get("query")
            if not isinstance(query, str) or not query.strip() or len(query) > 500:
                raise ValueError("INVALID_SEARCH_QUERY")
            scope = {path for path in self._path_policy(binding) if _safe_repository_path(path)}
            rows = self._search_code(query, scope)
            snippets = [
                row for row in rows[:10] if isinstance(row, dict) and row.get("path") in scope
            ]
            safe = build_context_pack(
                task={"id": binding["entity_id"], "title": "Authorized code search"},
                snippets=snippets,
                allowed_paths=scope,
                max_tokens=2000,
            )
            return {"results": safe.content["L2"], "sha256": safe.sha256}
        if tool == "read_artifact":
            if self._read_authorized_artifact is None:
                raise ToolDenied("ARTIFACT_ACCESS_UNAVAILABLE")
            reference = arguments.get("artifact_ref")
            offset, limit = arguments.get("offset", 0), arguments.get("limit", 100)
            if (
                not isinstance(reference, str)
                or not re.fullmatch(r"tool-outputs/[0-9a-f]{64}\.log", reference)
                or type(offset) is not int
                or type(limit) is not int
                or offset < 0
                or not 1 <= limit <= 100
            ):
                raise ValueError("INVALID_ARTIFACT_REQUEST")
            result = self._read_authorized_artifact(binding, reference, offset, limit)
            artifact_sha = result.get("sha256") if isinstance(result, dict) else None
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("lines"), list)
                or not isinstance(artifact_sha, str)
                or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha)
            ):
                raise ValueError("ARTIFACT_READER_RESPONSE_INVALID")
            safe = build_context_pack(
                task={"id": binding["entity_id"], "title": "Authorized artifact page"},
                snippets=[
                    {
                        "path": "artifact/output.log",
                        "blob_sha": artifact_sha,
                        "line": offset + 1,
                        "text": "\n".join(str(line) for line in result["lines"]),
                    }
                ],
                allowed_paths={"artifact/output.log"},
                max_tokens=2000,
            )
            return {
                "artifact_ref": reference,
                "offset": offset,
                "next_offset": result.get("next_offset"),
                "content": safe.content["L2"][0]["text"] if safe.content["L2"] else "",
                "context_sha256": safe.sha256,
            }
        if tool == "propose_task":
            title, description = arguments.get("title"), arguments.get("description")
            if (
                not isinstance(title, str)
                or not title.strip()
                or len(title) > 240
                or not isinstance(description, str)
                or not description.strip()
                or len(description) > 20_000
            ):
                raise ValueError("INVALID_TASK_PROPOSAL")
            proposal = TaskProposal(title=title.strip(), description=description.strip())
            stored = self._store_proposal(binding, proposal)
            return {"proposal": stored, "executable": False, "approval_required": True}
        raise ToolDenied("TOOL_NOT_ALLOWED")

    def _consume_quota(self, actor: str) -> None:
        now = self._clock()
        calls = self._calls[actor]
        while calls and now - calls[0] >= self._window:
            calls.popleft()
        if len(calls) >= self._max_calls:
            raise ToolDenied("TOOL_QUOTA_EXCEEDED")
        calls.append(now)

    @staticmethod
    def _sanitize(binding: dict, value: dict) -> dict:
        pack = build_context_pack(
            task={
                "id": binding["entity_id"],
                "title": json.dumps(value, sort_keys=True, default=str),
            },
            max_tokens=2000,
        )
        return pack.content["L0"]


def _safe_repository_path(path: str) -> bool:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        return False
    parts = path.split("/")
    if any(part in {"", ".", "..", ".git", ".ssh", ".aws", "secrets"} for part in parts):
        return False
    filename = parts[-1].casefold()
    return not (
        filename == ".env"
        or filename.startswith(".env.")
        and filename != ".env.example"
        or filename.endswith((".pem", ".key", ".p12", ".pfx"))
        or filename in {"id_rsa", "id_ed25519", "credentials.json"}
        or re.search(r"(?:^|/)secrets?(?:/|$)", path, re.IGNORECASE)
    )
