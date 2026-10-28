"""Small idempotent reconciliation pass over externally persisted task states."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from task_engine.models import Task
from task_engine.transitions import apply_transition

from factory_workers.retry_queue import schedule_failure


def reconcile_once(
    rows: Iterable[dict], *, is_lease_expired: Callable[[dict], bool],
    enqueue_retry: Callable[[str, str], bool],
) -> dict[str, int]:
    examined = scheduled = unchanged = 0
    for row in rows:
        examined += 1
        if row.get("status") != "running" or not is_lease_expired(row):
            unchanged += 1
            continue
        task_id, key = row.get("task_id"), row.get("operation_key")
        if not task_id or not key:
            unchanged += 1
            continue
        # Stable key makes repeated reconciliation harmless and never republishes side effects.
        scheduled += bool(enqueue_retry(task_id, f"reconcile:{key}"))
    return {"examined": examined, "retry_scheduled": scheduled, "unchanged": unchanged}


def reconcile_expired_task_leases(
    session: Session, *, now: datetime, max_attempts: int = 3
) -> dict[str, int]:
    """Atomically move expired runs to retry/DLQ without repeating committed effects."""
    tasks = session.scalars(
        select(Task)
        .where(Task.status == "running", Task.lease_expires_at <= now)
        .order_by(Task.lease_expires_at, Task.id)
        .with_for_update(skip_locked=True)
    ).all()
    retried = dead_lettered = moved_to_review = 0
    for task in tasks:
        result = task.result if isinstance(task.result, dict) else {}
        operation_key = f"run:{task.id}:{task.fencing_token}"
        if result.get("side_effect_committed") is True:
            apply_transition(
                session, task, entity_type="task", new_state="review",
                expected_version=task.state_version, actor="reconciler",
                reason="Expired run had a committed side effect; verify before replay.",
                idempotency_key=f"reconcile-review:{task.fencing_token}",
            )
            moved_to_review += 1
        else:
            attempt = result.get("attempt", 1)
            if type(attempt) is not int or attempt < 1:
                attempt = 1
            decision = schedule_failure(
                session,
                task_id=task.id,
                operation_key=operation_key,
                attempt=attempt,
                max_attempts=max_attempts,
                failure_kind="infrastructure_transient",
                now=now,
            )
            next_status = "failed" if decision.status == "dead_letter" else "retry_wait"
            apply_transition(
                session, task, entity_type="task", new_state=next_status,
                expected_version=task.state_version, actor="reconciler",
                reason="Worker lease expired; scheduled idempotent recovery.",
                idempotency_key=f"reconcile:{task.fencing_token}",
            )
            dead_lettered += decision.status == "dead_letter"
            retried += decision.status == "retry_wait"
        task.lease_owner = None
        task.lease_expires_at = None
    return {
        "examined": len(tasks), "retry_scheduled": retried,
        "dead_lettered": dead_lettered, "moved_to_review": moved_to_review,
    }


def run_reconciler_once(session_factory, *, now: datetime) -> dict[str, int]:
    """Transactional one-shot entrypoint for a local periodic scheduler or cron."""
    with session_factory.begin() as session:
        return reconcile_expired_task_leases(session, now=now)
