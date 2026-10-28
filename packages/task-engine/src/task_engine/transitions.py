from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from task_engine.models import (
    Demand,
    RequirementRevision,
    Task,
    TaskDependency,
    TransitionEvent,
)


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
        if (
            prior.to_state != new_state
            or prior.expected_version != expected_version
            or prior.actor != actor.strip()
            or prior.reason != reason.strip()
        ):
            raise TransitionError("IDEMPOTENCY_KEY_REUSED")
        return prior
    if entity.state_version != expected_version:
        raise TransitionError("STALE_VERSION")
    old_state = entity.status
    if new_state not in TRANSITIONS[entity_type].get(old_state, set()):
        raise TransitionError("INVALID_TRANSITION")
    if entity_type == "task":
        task = entity
        lease_expiry = task.lease_expires_at
        if lease_expiry is not None and lease_expiry.tzinfo is None:
            lease_expiry = lease_expiry.replace(tzinfo=UTC)
        if new_state in {"ready", "leased", "running", "review", "done"}:
            from sqlalchemy.orm import aliased

            dependency = aliased(Task)
            open_dependency = session.scalar(
                select(
                    exists().where(
                        TaskDependency.task_id == task.id,
                        TaskDependency.depends_on_id == dependency.id,
                        dependency.status != "done",
                    )
                )
            )
            if open_dependency:
                raise TransitionError("TASK_DEPENDENCIES_INCOMPLETE")
        if new_state == "done":
            from task_engine.execution import ExecutionError
            from task_engine.runs import RunProvenanceError, assert_completion_evidence

            try:
                assert_completion_evidence(session, task)
            except (ExecutionError, RunProvenanceError) as exc:
                raise TransitionError(str(exc)) from exc
        if new_state == "running" and (
            not task.lease_owner or lease_expiry is None or lease_expiry <= datetime.now(UTC)
        ):
            raise TransitionError("ACTIVE_LEASE_REQUIRED")
        if new_state == "review" and task.result is None:
            raise TransitionError("TASK_RESULT_REQUIRED")
    elif new_state == "completed":
        task_count = session.scalar(select(Task.id).where(Task.demand_id == entity.id).limit(1))
        pending_tasks = session.scalar(
            select(exists().where(Task.demand_id == entity.id, Task.status != "done"))
        )
        latest_revision = session.scalar(
            select(RequirementRevision)
            .where(RequirementRevision.demand_id == entity.id)
            .order_by(RequirementRevision.version.desc())
            .limit(1)
        )
        if not task_count or pending_tasks:
            raise TransitionError("DEMAND_TASKS_INCOMPLETE")
        if latest_revision is None or latest_revision.decision != "approved":
            raise TransitionError("DEMAND_APPROVAL_REQUIRED")
        from task_engine.execution import ExecutionError
        from task_engine.runs import RunProvenanceError, assert_completion_evidence

        try:
            for task in session.scalars(select(Task).where(Task.demand_id == entity.id)):
                assert_completion_evidence(session, task)
        except (ExecutionError, RunProvenanceError) as exc:
            raise TransitionError("DEMAND_APPROVAL_REQUIRED") from exc
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
    conditions = [
        expected_entity.id == entity.id,
        expected_entity.state_version == expected_version,
        expected_entity.status == old_state,
    ]
    if entity_type == "task" and new_state == "running":
        conditions.extend(
            [
                Task.lease_owner.is_not(None),
                Task.lease_expires_at > datetime.now(UTC),
                Task.lease_owner == entity.lease_owner,
                Task.fencing_token == entity.fencing_token,
            ]
        )
    values: dict[str, object] = {
        "status": new_state,
        "state_version": expected_entity.state_version + 1,
    }
    if entity_type == "task" and new_state == "ready":
        # A retry starts a new attempt; the previous run result must not be
        # visible as the result of the work that is about to execute.
        values["result"] = None
    update_result = session.execute(update(expected_entity).where(*conditions).values(**values))
    if update_result.rowcount != 1:
        concurrent_replay = session.scalar(
            select(TransitionEvent).where(
                TransitionEvent.entity_type == entity_type,
                TransitionEvent.entity_id == entity.id,
                TransitionEvent.idempotency_key == idempotency_key.strip(),
            )
        )
        if concurrent_replay is not None and (
            concurrent_replay.to_state == new_state
            and concurrent_replay.expected_version == expected_version
            and concurrent_replay.actor == actor.strip()
            and concurrent_replay.reason == reason.strip()
        ):
            return concurrent_replay
        raise TransitionError("STALE_VERSION")
    session.add(event)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise TransitionError("TRANSITION_CONFLICT") from None
    session.refresh(entity)
    return event
