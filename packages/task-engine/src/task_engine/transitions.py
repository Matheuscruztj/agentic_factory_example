from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.models import Demand, Task, TransitionEvent


class TransitionError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


TRANSITIONS = {
    "demand": {
        "new": {"triage", "cancelled"},
        "triage": {"discovery", "blocked", "cancelled"},
        "discovery": {"clarification_pending", "refined", "blocked", "failed"},
        "clarification_pending": {"discovery", "cancelled"},
        "refined": {"approved", "discovery", "cancelled"},
        "approved": {"planned", "cancelled"},
        "planned": {"executing", "cancelled"},
        "executing": {"verifying", "blocked", "failed"},
        "verifying": {"human_review", "executing", "failed"},
        "human_review": {"completed", "executing", "follow_up_required"},
        "blocked": {"triage", "discovery", "executing", "cancelled"},
        "failed": {"triage", "cancelled"},
        "follow_up_required": {"completed"},
        "completed": set(),
        "cancelled": set(),
    },
    "task": {
        "proposed": {"ready", "blocked", "cancelled"},
        "ready": {"leased", "blocked", "cancelled"},
        "leased": {"running", "ready", "retry_wait", "failed"},
        "running": {"review", "blocked", "retry_wait", "failed"},
        "review": {"done", "ready", "failed"},
        "blocked": {"ready", "cancelled"},
        "retry_wait": {"ready", "failed", "cancelled"},
        "failed": {"ready", "cancelled"},
        "done": set(),
        "cancelled": set(),
    },
}


def apply_transition(
    session: Session,
    entity: Demand | Task,
    *,
    entity_type: str,
    new_state: str,
    expected_version: int,
    actor: str,
    reason: str,
    idempotency_key: str,
) -> TransitionEvent:
    if (
        entity_type not in TRANSITIONS
        or not actor.strip()
        or not reason.strip()
        or not idempotency_key.strip()
    ):
        raise TransitionError("TRANSITION_METADATA_REQUIRED")
    expected_entity = Demand if entity_type == "demand" else Task
    if not isinstance(entity, expected_entity):
        raise TransitionError("TRANSITION_ENTITY_TYPE_MISMATCH")
    prior = session.scalar(
        select(TransitionEvent).where(
            TransitionEvent.entity_type == entity_type,
            TransitionEvent.entity_id == entity.id,
            TransitionEvent.idempotency_key == idempotency_key,
        )
    )
    if prior:
        if prior.to_state != new_state:
            raise TransitionError("IDEMPOTENCY_KEY_REUSED")
        return prior
    if entity.state_version != expected_version:
        raise TransitionError("STALE_VERSION")
    old_state = entity.status
    if new_state not in TRANSITIONS[entity_type].get(old_state, set()):
        raise TransitionError("INVALID_TRANSITION")
    event = TransitionEvent(
        entity_type=entity_type,
        entity_id=entity.id,
        from_state=old_state,
        to_state=new_state,
        expected_version=expected_version,
        actor=actor.strip(),
        reason=reason.strip(),
        idempotency_key=idempotency_key.strip(),
    )
    entity.status = new_state
    entity.state_version += 1
    session.add(event)
    session.flush()
    return event
