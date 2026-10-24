"""Atomic task leases with monotonically increasing fencing tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.orm import Session

from task_engine.models import Task, TaskDependency


class LeaseError(ValueError):
    pass


def claim_task(
    session: Session,
    worker_id: str,
    *,
    demand_id: str | None = None,
    ttl: timedelta = timedelta(minutes=2),
) -> Task | None:
    if not worker_id.strip() or ttl.total_seconds() <= 0:
        raise LeaseError("INVALID_LEASE_REQUEST")
    now = datetime.now(UTC)
    # Alias the dependency task so the correlated subquery references its parent task.
    from sqlalchemy.orm import aliased

    parent = aliased(Task)
    dependency_open = exists(
        select(TaskDependency.id)
        .join(parent, parent.id == TaskDependency.depends_on_id)
        .where(TaskDependency.task_id == Task.id, parent.status != "done")
    )
    candidate = session.scalar(
        select(Task.id)
        .where(
            *((Task.demand_id == demand_id,) if demand_id else ()),
            or_(
                Task.status == "ready",
                and_(Task.status.in_(("leased", "running")), Task.lease_expires_at <= now),
            ),
            ~dependency_open,
        )
        .order_by(Task.priority.desc(), Task.created_at, Task.id)
        .limit(1)
    )
    if candidate is None:
        return None
    result = session.execute(
        update(Task)
        .where(
            Task.id == candidate,
            *((Task.demand_id == demand_id,) if demand_id else ()),
            or_(
                Task.status == "ready",
                and_(Task.status.in_(("leased", "running")), Task.lease_expires_at <= now),
            ),
        )
        .values(
            status="leased",
            lease_owner=worker_id.strip(),
            lease_expires_at=now + ttl,
            fencing_token=Task.fencing_token + 1,
            state_version=Task.state_version + 1,
        )
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount != 1:
        return None
    session.flush()
    return session.get(Task, candidate)


def heartbeat(
    session: Session,
    task_id: str,
    worker_id: str,
    fencing_token: int,
    *,
    ttl: timedelta = timedelta(minutes=2),
) -> datetime:
    now = datetime.now(UTC)
    expiry = now + ttl
    result = session.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.status == "leased",
            Task.lease_owner == worker_id,
            Task.fencing_token == fencing_token,
            Task.lease_expires_at > now,
        )
        .values(lease_expires_at=expiry)
    )
    if result.rowcount != 1:
        raise LeaseError("LEASE_LOST")
    return expiry


def assert_lease(session: Session, task_id: str, worker_id: str, fencing_token: int) -> Task:
    now = datetime.now(UTC)
    task = session.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.lease_owner == worker_id,
            Task.fencing_token == fencing_token,
            Task.lease_expires_at > now,
            Task.status.in_(("leased", "running")),
        )
    )
    if task is None:
        raise LeaseError("LEASE_LOST")
    return task


def commit_worker_result(
    session: Session, task_id: str, worker_id: str, fencing_token: int, *, result: dict
) -> Task:
    """Fence stale workers before accepting their result; caller owns transaction."""
    task = assert_lease(session, task_id, worker_id, fencing_token)
    task.status = "review"
    task.result = result
    task.state_version += 1
    task.lease_owner = None
    task.lease_expires_at = None
    # Result is intentionally returned to the caller for domain-specific persistence.
    session.flush()
    return task
