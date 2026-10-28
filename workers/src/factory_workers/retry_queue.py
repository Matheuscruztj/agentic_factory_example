"""PostgreSQL-backed retry and dead-letter records for durable workers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from task_engine.models import RetryQueueEntry

from factory_workers.retries import FailureKind, plan_retry


@dataclass(frozen=True, slots=True)
class RetryableOperationError(RuntimeError):
    kind: FailureKind


def run_retry_batch(
    session_factory,
    *,
    worker_id: str,
    now: datetime,
    execute: Callable[[str, str], None],
    limit: int = 50,
) -> dict[str, int]:
    """Lease due work, run with stable idempotency keys, and persist each result."""
    with session_factory.begin() as session:
        claimed = claim_due_retries(
            session, now=now, worker_id=worker_id, limit=limit
        )
        snapshots = [
            (row.id, row.task_id, row.operation_key, row.failed_attempt,
             row.max_attempts, row.idempotency_key)
            for row in claimed
        ]
    completed = dead_lettered = retried = 0
    for row_id, task_id, operation_key, failed_attempt, max_attempts, key in snapshots:
        try:
            execute(task_id, key)
        except RetryableOperationError as exc:
            with session_factory.begin() as session:
                row = session.get(RetryQueueEntry, row_id)
                if row is None or row.claimed_by != worker_id:
                    continue
                complete_retry(row, worker_id=worker_id, now=now)
                following = schedule_failure(
                    session, task_id=task_id, operation_key=operation_key,
                    attempt=failed_attempt + 1, max_attempts=max_attempts,
                    failure_kind=exc.kind, now=now,
                )
                dead_lettered += following.status == "dead_letter"
                retried += following.status == "retry_wait"
        except Exception:
            with session_factory.begin() as session:
                row = session.get(RetryQueueEntry, row_id)
                if row is None or row.claimed_by != worker_id:
                    continue
                complete_retry(row, worker_id=worker_id, now=now)
                following = schedule_failure(
                    session, task_id=task_id, operation_key=operation_key,
                    attempt=failed_attempt + 1, max_attempts=max_attempts,
                    failure_kind="infrastructure_transient", now=now,
                )
                dead_lettered += following.status == "dead_letter"
                retried += following.status == "retry_wait"
        else:
            with session_factory.begin() as session:
                row = session.get(RetryQueueEntry, row_id)
                if row is not None and row.claimed_by == worker_id:
                    complete_retry(row, worker_id=worker_id, now=now)
                    completed += 1
    return {"claimed": len(snapshots), "completed": completed,
            "retry_scheduled": retried, "dead_lettered": dead_lettered}


def schedule_failure(
    session: Session,
    *,
    task_id: str,
    operation_key: str,
    attempt: int,
    max_attempts: int,
    failure_kind: FailureKind,
    now: datetime,
) -> RetryQueueEntry:
    """Persist a retry/DLQ item idempotently; caller controls the transaction."""
    decision = plan_retry(
        task_id=task_id,
        operation_key=operation_key,
        attempt=attempt,
        max_attempts=max_attempts,
        now=now,
        failure_kind=failure_kind,
    )
    existing = session.scalar(select(RetryQueueEntry).where(
        RetryQueueEntry.task_id == task_id,
        RetryQueueEntry.operation_key == operation_key,
        RetryQueueEntry.failed_attempt == attempt,
    ))
    if existing is not None:
        return existing
    row = RetryQueueEntry(
        task_id=task_id,
        operation_key=operation_key,
        failed_attempt=attempt,
        max_attempts=max_attempts,
        failure_kind=failure_kind,
        status=decision.state,
        available_at=decision.available_at,
        idempotency_key=decision.idempotency_key,
    )
    session.add(row)
    session.flush()
    return row


def claim_due_retries(
    session: Session, *, now: datetime, worker_id: str, limit: int = 50,
    lease_seconds: int = 60,
) -> list[RetryQueueEntry]:
    """Select due retry events under row locks; keep transaction open through dispatch."""
    if not worker_id or not 1 <= limit <= 500 or not 1 <= lease_seconds <= 3600:
        raise ValueError("INVALID_RETRY_BATCH_SIZE")
    rows = session.scalars(
        select(RetryQueueEntry)
        .where(
            RetryQueueEntry.status == "retry_wait",
            RetryQueueEntry.available_at <= now,
            (RetryQueueEntry.claim_expires_at.is_(None)
             | (RetryQueueEntry.claim_expires_at <= now)),
        )
        .order_by(RetryQueueEntry.available_at, RetryQueueEntry.id)
        .with_for_update(skip_locked=True)
        .limit(limit)
    ).all()
    for row in rows:
        row.claimed_by = worker_id
        row.claim_expires_at = now + timedelta(seconds=lease_seconds)
    session.flush()
    return list(rows)


def complete_retry(
    row: RetryQueueEntry, *, worker_id: str, now: datetime | None = None
) -> None:
    """Acknowledge only after the idempotent operation committed successfully."""
    if row.claimed_by != worker_id:
        raise PermissionError("RETRY_CLAIM_OWNER_MISMATCH")
    row.status = "completed"
    row.completed_at = now or datetime.now(UTC)
    row.claimed_by = None
    row.claim_expires_at = None
