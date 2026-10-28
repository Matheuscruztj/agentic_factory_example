"""Deterministic fake scheduler used for local vertical-slice simulations."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.audit import record_audit
from task_engine.leases import assert_lease, claim_task, commit_worker_result, heartbeat
from task_engine.models import Task
from task_engine.outbox import consume_once, enqueue_event


def run_one_fake_step(
    session: Session, worker_id: str = "fake-worker", *, demand_id: str | None = None
) -> str | None:
    task = claim_task(session, worker_id, demand_id=demand_id, ttl=timedelta(minutes=5))
    if task is None:
        return None
    token = task.fencing_token
    heartbeat(session, task.id, worker_id, token, ttl=timedelta(minutes=5))
    assert_lease(session, task.id, worker_id, token)
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
    record_audit(
        session,
        subject_type="task",
        subject_id=task.id,
        action="fake_task_review_result",
        actor=worker_id,
        details={"checks": checks, "fencing_token": token},
    )
    event_id = f"task-review:{task.id}:{token}"
    enqueue_event(session, event_id, "task.reviewed", {"task_id": task.id, "checks": checks})
    return task.id


def run_fake_demand(
    session: Session, demand_id: str, *, worker_id: str = "fake-worker"
) -> list[str]:
    """Run fake steps until blocked; fake results stop at review and never complete tasks."""
    reviewed: list[str] = []
    while True:
        task_id = run_one_fake_step(session, worker_id, demand_id=demand_id)
        if task_id is None:
            break
        reviewed.append(task_id)
        # Simulate redelivery of the same review event in the same transaction.
        task = session.get(Task, task_id)
        event_id = f"task-review:{task_id}:{task.fencing_token}"
        consume_once(session, event_id, lambda: {"task_id": task_id, "accepted": True})
        consume_once(session, event_id, lambda: {"task_id": task_id, "accepted": True})
    remaining = session.scalars(
        select(Task).where(Task.demand_id == demand_id, Task.status != "done")
    ).all()
    record_audit(
        session,
        subject_type="demand",
        subject_id=demand_id,
        action="fake_demand_simulation_idle",
        actor=worker_id,
        details={
            "fake_steps": len(reviewed),
            "approval_simulated": False,
            "pending_tasks": len(remaining),
        },
    )
    return reviewed
