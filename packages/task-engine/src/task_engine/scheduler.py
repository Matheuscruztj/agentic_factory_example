"""Deterministic fake scheduler used for local vertical-slice simulations."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.audit import record_audit
from task_engine.leases import claim_task, commit_worker_result
from task_engine.models import Task
from task_engine.outbox import consume_once, enqueue_event


def run_one_fake_step(
    session: Session, worker_id: str = "fake-worker", *, demand_id: str | None = None
) -> str | None:
    task = claim_task(session, worker_id, demand_id=demand_id, ttl=timedelta(minutes=5))
    if task is None:
        return None
    token = task.fencing_token
    task.status = "running"
    task.state_version += 1
    role = task.owner_role.lower()
    checks = {
        "analyst": ["requirements-present"],
        "backend": ["fake-unit-check"],
        "qa": ["fake-acceptance-check"],
    }.get(role, ["fake-check"])
    commit_worker_result(
        session, task.id, worker_id, token, result={"checks": checks, "model_called": False}
    )
    task.status = "done"
    task.state_version += 1
    task.result = {"checks": checks, "model_called": False}
    task.lease_owner = None
    task.lease_expires_at = None
    record_audit(
        session,
        subject_type="task",
        subject_id=task.id,
        action="fake_task_completed",
        actor=worker_id,
        details={"checks": checks, "fencing_token": token},
    )
    event_id = f"task-done:{task.id}:{token}"
    enqueue_event(session, event_id, "task.completed", {"task_id": task.id, "checks": checks})
    return task.id


def run_fake_demand(
    session: Session, demand_id: str, *, worker_id: str = "fake-worker"
) -> list[str]:
    """Run ready DAG nodes until blocked/completed; duplicate event delivery is harmless."""
    completed: list[str] = []
    while True:
        task_id = run_one_fake_step(session, worker_id, demand_id=demand_id)
        if task_id is None:
            break
        completed.append(task_id)
        # Simulate redelivery of the same completion event in the same transaction.
        task = session.get(Task, task_id)
        event_id = f"task-done:{task_id}:{task.fencing_token}"
        consume_once(session, event_id, lambda: {"task_id": task_id, "accepted": True})
        consume_once(session, event_id, lambda: {"task_id": task_id, "accepted": True})
    remaining = session.scalars(
        select(Task).where(Task.demand_id == demand_id, Task.status != "done")
    ).all()
    if not remaining:
        record_audit(
            session,
            subject_type="demand",
            subject_id=demand_id,
            action="fake_demand_completed",
            actor=worker_id,
            details={"tasks_completed": len(completed), "approval_simulated": True},
        )
    return completed
