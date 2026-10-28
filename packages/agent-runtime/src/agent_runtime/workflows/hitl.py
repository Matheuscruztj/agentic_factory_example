"""LangGraph human interrupt/resume helpers backed by the durable checkpointer."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def require_human_decision(
    request: dict[str, Any],
    *,
    approval_lookup: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    try:
        from langgraph.types import interrupt
    except ImportError as exc:
        raise RuntimeError("INSTALL_AGENT_RUNTIME_WITH_LANGGRAPH_EXTRAS") from exc
    decision = interrupt({"type": "approval", **request})
    if not isinstance(decision, dict) or decision.get("decision") not in {
        "approved",
        "rejected",
        "changes_requested",
    }:
        raise ValueError("INVALID_HUMAN_DECISION")
    if not decision.get("actor") or not decision.get("approval_id"):
        raise ValueError("HUMAN_DECISION_AUDIT_FIELDS_REQUIRED")
    if approval_lookup is None:
        raise RuntimeError("PERSISTED_APPROVAL_LOOKUP_REQUIRED")
    approval = approval_lookup(decision["approval_id"])
    if approval is None:
        raise PermissionError("PERSISTED_APPROVAL_NOT_FOUND")

    def field(name: str) -> Any:
        if isinstance(approval, dict):
            return approval.get(name)
        return getattr(approval, name, None)

    expected = {
        "entity_type": request.get("entity_type"),
        "entity_id": request.get("entity_id"),
        "entity_version": request.get("entity_version"),
        "payload_hash": request.get("payload_hash"),
    }
    if not all(value is not None for value in expected.values()):
        raise ValueError("APPROVAL_SUBJECT_BINDING_REQUIRED")
    if any(field(name) != value for name, value in expected.items()):
        raise PermissionError("APPROVAL_SUBJECT_CHANGED")
    actor = field("decision_by")
    if (
        field("id") != decision["approval_id"]
        or field("status") != decision["decision"]
        or not actor
        or actor != decision["actor"]
        or field("requested_by") == actor
    ):
        raise PermissionError("PERSISTED_APPROVAL_DECISION_MISMATCH")
    return {**decision, "actor": actor}


def resume_config(run_id: str) -> dict[str, dict[str, str]]:
    if not run_id or len(run_id) > 255:
        raise ValueError("INVALID_RUN_ID")
    return {"configurable": {"thread_id": run_id}}
