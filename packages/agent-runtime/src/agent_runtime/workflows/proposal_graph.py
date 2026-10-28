"""Turn reviewed proposals into tasks and resume against their captured context."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any


def follow_up(
    proposal: dict[str, Any],
    *,
    approval: dict[str, Any],
    create_task: Callable[[dict[str, Any]], str],
    invoke_subworkflow: Callable[[str, dict[str, Any]], Any],
    validate_scope: Callable[[Mapping[str, Any]], bool] | None = None,
) -> Any:
    """Create a follow-up only after matching human approval; reuse its snapshot."""
    if approval.get("status") != "approved":
        raise PermissionError("HUMAN_APPROVAL_REQUIRED")
    if (
        approval.get("proposal_id") != proposal.get("id")
        or approval.get("payload_hash") != proposal.get("payload_hash")
    ):
        raise ValueError("APPROVAL_PROPOSAL_MISMATCH")
    snapshot_sha = proposal.get("snapshot_sha")
    if not isinstance(snapshot_sha, str) or len(snapshot_sha) not in {40, 64} or any(
        char not in "0123456789abcdef" for char in snapshot_sha
    ):
        raise ValueError("PROPOSAL_SNAPSHOT_REQUIRED")
    proposed = proposal.get("proposed_task")
    if proposed is not None:
        if not isinstance(proposed, Mapping):
            raise ValueError("PROPOSED_TASK_INVALID")
        dependencies = proposed.get("depends_on", [])
        scopes = proposed.get("path_scopes", [])
        risk = proposed.get("risk")
        if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)):
            raise ValueError("PROPOSAL_DEPENDENCIES_INVALID")
        if not isinstance(scopes, Sequence) or isinstance(scopes, (str, bytes)) or not scopes:
            raise ValueError("PROPOSAL_SCOPE_REQUIRED")
        if risk not in {"low", "normal", "high", "critical"}:
            raise ValueError("PROPOSAL_RISK_INVALID")
        if validate_scope is not None and not validate_scope(proposed):
            raise PermissionError("PROPOSAL_SCOPE_NOT_ALLOWED")
    elif validate_scope is not None:
        raise ValueError("PROPOSED_TASK_REQUIRED")
    task_id = create_task(proposal)
    if not isinstance(task_id, str) or not task_id.strip():
        raise RuntimeError("FOLLOW_UP_TASK_NOT_CREATED")
    return invoke_subworkflow(task_id, {"snapshot_sha": snapshot_sha, "discovery": "reuse"})
