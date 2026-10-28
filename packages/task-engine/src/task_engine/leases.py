"""Atomic task leases with monotonically increasing fencing tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, delete, exists, func, or_, select, update
from sqlalchemy.orm import Session

from task_engine.models import Task, TaskDependency, TaskPathLease

PRIORITY_AGING_AFTER = timedelta(minutes=30)


class LeaseError(ValueError):
    pass


def claim_task(
    session: Session,
    worker_id: str,
    *,
    demand_id: str | None = None,
    ttl: timedelta = timedelta(minutes=2),
    require_execution_spec: bool = False,
) -> Task | None:
    if not worker_id.strip() or ttl.total_seconds() <= 0:
        raise LeaseError("INVALID_LEASE_REQUEST")
    now = datetime.now(UTC)
    # Serialize the short claim transaction so the path-overlap check and lease
    # reservation are atomic across workers. Execution itself never holds a DB lock.
    if session.get_bind().dialect.name == "postgresql":
        session.execute(select(func.pg_advisory_xact_lock(0x4146414250415448)))
    # Alias the dependency task so the correlated subquery references its parent task.
    from sqlalchemy.orm import aliased

    parent = aliased(Task)
    dependency_open = exists(
        select(TaskDependency.id)
        .join(parent, parent.id == TaskDependency.depends_on_id)
        .where(TaskDependency.task_id == Task.id, parent.status != "done")
    )
    candidates = session.scalars(
        select(Task)
        .where(
            *((Task.demand_id == demand_id,) if demand_id else ()),
            or_(
                Task.status == "ready",
                and_(Task.status.in_(("leased", "running")), Task.lease_expires_at <= now),
            ),
            ~dependency_open,
        )
        # Priority applies while work is fresh. Once a task has waited long
        # enough, FIFO aging takes precedence so a stream of urgent work cannot
        # starve it indefinitely.
        .order_by(
            case((Task.created_at <= now - PRIORITY_AGING_AFTER, 0), else_=1),
            case(
                (Task.created_at <= now - PRIORITY_AGING_AFTER, Task.created_at),
                else_=None,
            ),
            Task.priority.desc(),
            Task.created_at,
            Task.id,
        )
    ).all()
    candidate = None
    scopes: tuple[str, ...] = ()
    for task in candidates:
        if require_execution_spec and not task.execution_spec:
            continue
        task_scopes = _validated_scopes(task.path_scopes)
        active = session.scalars(
            select(TaskPathLease.scope)
            .join(Task, Task.id == TaskPathLease.task_id)
            .where(
                TaskPathLease.task_id != task.id,
                TaskPathLease.expires_at > now,
                Task.status.in_(("leased", "running")),
                Task.lease_expires_at > now,
            )
        ).all()
        if not any(_scope_overlaps(left, right) for left in task_scopes for right in active):
            candidate, scopes = task, task_scopes
            break
    if candidate is None:
        return None
    session.execute(delete(TaskPathLease).where(TaskPathLease.task_id == candidate.id))
    result = session.execute(
        update(Task)
        .where(
            Task.id == candidate.id,
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
    if getattr(result, "rowcount", None) != 1:
        return None
    for scope in scopes:
        session.add(TaskPathLease(task_id=candidate.id, scope=scope, expires_at=now + ttl))
    session.flush()
    return session.get(Task, candidate.id)


def heartbeat(
    session: Session,
    task_id: str,
    worker_id: str,
    fencing_token: int,
    *,
    ttl: timedelta = timedelta(minutes=2),
) -> datetime:
    if not worker_id.strip() or ttl.total_seconds() <= 0:
        raise LeaseError("INVALID_LEASE_REQUEST")
    now = datetime.now(UTC)
    expiry = now + ttl
    result = session.execute(
        update(Task)
        .where(
            Task.id == task_id,
            Task.status.in_(("leased", "running")),
            Task.lease_owner == worker_id,
            Task.fencing_token == fencing_token,
            Task.lease_expires_at > now,
        )
        .values(lease_expires_at=expiry)
        .execution_options(synchronize_session=False)
    )
    if getattr(result, "rowcount", None) != 1:
        raise LeaseError("LEASE_LOST")
    session.execute(
        update(TaskPathLease).where(TaskPathLease.task_id == task_id).values(expires_at=expiry)
    )
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
    session.execute(delete(TaskPathLease).where(TaskPathLease.task_id == task_id))
    # Result is intentionally returned to the caller for domain-specific persistence.
    session.flush()
    return task


def _validated_scopes(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise LeaseError("INVALID_PATH_SCOPE")
    scopes: list[str] = []
    for raw in value:
        if (
            not isinstance(raw, str)
            or not raw
            or len(raw) > 500
            or raw.startswith("/")
            or "\\" in raw
            or "\x00" in raw
            or any(part in {"", ".", ".."} for part in raw.rstrip("/").split("/"))
        ):
            raise LeaseError("INVALID_PATH_SCOPE")
        normalized = raw.rstrip("/")
        if any(character in normalized for character in "*?"):
            supported = normalized.endswith(("/**", "/*"))
            prefix = normalized[:-3] if normalized.endswith("/**") else normalized[:-2]
            if not supported or any(character in prefix for character in "*?"):
                raise LeaseError("INVALID_PATH_SCOPE")
        scopes.append(normalized)
    return tuple(sorted(set(scopes)))


def _scope_overlaps(left: str, right: str) -> bool:
    """Recognize exact files and directory scopes expressed as terminal `/**`."""
    if left == right:
        return True
    for subtree, other in ((left, right), (right, left)):
        if subtree.endswith("/**"):
            root = subtree[:-3].rstrip("/")
            candidate = other.removesuffix("/**").removesuffix("/*").rstrip("/")
            if candidate == root or candidate.startswith(root + "/"):
                return True
        if subtree.endswith("/*"):
            root = subtree[:-2].rstrip("/")
            candidate = other.removesuffix("/**").removesuffix("/*").rstrip("/")
            relative = (
                candidate[len(root) :].lstrip("/") if candidate.startswith(root + "/") else ""
            )
            if relative and "/" not in relative:
                return True
    return False
