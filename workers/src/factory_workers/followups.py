"""Idempotent delivery of human-approved follow-up tasks to subworkflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from task_engine.models import (
    ConversationTaskProposal,
    EventInbox,
    EventOutbox,
    Task,
)


def dispatch_approved_follow_up(
    session_factory,
    *,
    event_id: str,
    invoke_subworkflow: Callable[[str, str, dict], str],
) -> dict[str, str]:
    """Deliver the exact accepted proposal; retries reuse the event as graph run key."""
    with session_factory() as session:
        event = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == event_id).with_for_update()
        )
        if event is None or event.event_type != "task.follow_up.approved":
            raise ValueError("APPROVED_FOLLOW_UP_EVENT_REQUIRED")
        inbox = session.get(EventInbox, event_id)
        if inbox is not None:
            return {"status": "already_dispatched", **inbox.result}
        if event.published_at is not None:
            raise ValueError("FOLLOW_UP_EVENT_ALREADY_PUBLISHED")
        payload = event.payload
        proposal = session.get(ConversationTaskProposal, payload.get("proposal_id"))
        task = session.get(Task, payload.get("task_id"))
        if (
            proposal is None
            or task is None
            or proposal.status != "accepted"
            or proposal.created_task_id != task.id
            or proposal.payload_hash != payload.get("approval_hash")
            or event_id != f"proposal-follow-up:{proposal.id}"
            or task.demand_id != payload.get("demand_id")
            or not task.path_scopes
            or not task.acceptance
        ):
            raise ValueError("FOLLOW_UP_APPROVAL_BINDING_INVALID")
        snapshot_sha = payload.get("snapshot_sha")
        if not isinstance(snapshot_sha, str) or len(snapshot_sha) not in (40, 64):
            raise ValueError("FOLLOW_UP_SNAPSHOT_INVALID")
        result = invoke_subworkflow(
            event_id,
            task.id,
            {"snapshot_sha": snapshot_sha, "discovery": "reuse", "idempotency_key": event_id},
        )
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError("FOLLOW_UP_SUBWORKFLOW_NOT_STARTED")
        session.add(EventInbox(event_id=event_id, result={"run_id": result, "task_id": task.id}))
        event.published_at = datetime.now(UTC)
        event.attempts += 1
        session.commit()
        return {"status": "dispatched", "run_id": result, "task_id": task.id}
