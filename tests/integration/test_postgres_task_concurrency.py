from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from task_engine.leases import LeaseError, claim_task, commit_worker_result, heartbeat
from task_engine.models import (
    ApprovalRequest,
    Demand,
    RequirementRevision,
    Task,
    TaskDependency,
    TaskPathLease,
    TransitionEvent,
)
from task_engine.transitions import TransitionError, apply_transition


def _engine_or_skip():
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("PostgreSQL DATABASE_URL is required for multi-session acceptance")
    from sqlalchemy import create_engine

    return create_engine(url, pool_pre_ping=True)


def _cleanup(engine, demand_id: str) -> None:
    with Session(engine) as session:
        task_ids = select_task_ids(session, demand_id)
        session.execute(delete(TaskDependency).where(
            (TaskDependency.task_id.in_(task_ids)) | (TaskDependency.depends_on_id.in_(task_ids))
        ))
        session.execute(delete(TransitionEvent).where(
            TransitionEvent.entity_id.in_([demand_id, *task_ids])
        ))
        session.execute(delete(ApprovalRequest).where(
            ApprovalRequest.entity_id == demand_id
        ))
        session.execute(delete(RequirementRevision).where(
            RequirementRevision.demand_id == demand_id
        ))
        session.execute(delete(Task).where(Task.demand_id == demand_id))
        session.execute(delete(Demand).where(Demand.id == demand_id))
        session.commit()


def select_task_ids(session: Session, demand_id: str) -> list[str]:
    return list(session.scalars(select(Task.id).where(Task.demand_id == demand_id)).all())


def _new_demand(session: Session) -> Demand:
    row = Demand(
        source="acceptance",
        external_id=f"postgres-concurrency-{uuid4()}",
        title="Synthetic PostgreSQL concurrency acceptance",
        demand_type="feature",
    )
    session.add(row)
    session.commit()
    return row


def test_postgres_two_sessions_allow_only_one_same_version_transition() -> None:
    engine = _engine_or_skip()
    with Session(engine) as session:
        demand = _new_demand(session)
        demand_id = demand.id
    barrier = Barrier(2)

    def transition(actor: str) -> str:
        with Session(engine) as session:
            entity = session.get(Demand, demand_id)
            assert entity is not None
            barrier.wait(timeout=5)
            try:
                apply_transition(
                    session,
                    entity,
                    entity_type="demand",
                    new_state="triage",
                    expected_version=1,
                    actor=actor,
                    reason="concurrent acceptance",
                    idempotency_key=f"{actor}-{uuid4()}",
                )
                session.commit()
                return "won"
            except TransitionError as exc:
                session.rollback()
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(transition, ("reviewer-a", "reviewer-b")))
        assert results.count("won") == 1
        assert results.count("STALE_VERSION") == 1
        with Session(engine) as session:
            assert session.get(Demand, demand_id).state_version == 2
    finally:
        _cleanup(engine, demand_id)
        engine.dispose()


def test_postgres_two_workers_cannot_claim_same_task_concurrently() -> None:
    engine = _engine_or_skip()
    with Session(engine) as session:
        demand = _new_demand(session)
        task = Task(
            demand_id=demand.id,
            title="Synthetic concurrent claim acceptance",
            owner_role="backend",
            status="ready",
        )
        session.add(task)
        session.commit()
        demand_id, task_id = demand.id, task.id
    barrier = Barrier(2)

    def claim(worker: str) -> tuple[str, str | None]:
        with Session(engine) as session:
            barrier.wait(timeout=5)
            task = claim_task(
                session, worker, demand_id=demand_id, ttl=timedelta(seconds=20)
            )
            if task is None:
                session.rollback()
                return worker, None
            claimed_id = task.id
            session.commit()
            return worker, claimed_id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ("worker-claim-a", "worker-claim-b")))
        claims = [task_id for _, task_id in results if task_id is not None]
        assert claims == [task_id]
        with Session(engine) as session:
            claimed = session.get(Task, task_id)
            assert claimed is not None
            assert claimed.lease_owner in {"worker-claim-a", "worker-claim-b"}
            assert claimed.fencing_token == 1
    finally:
        _cleanup(engine, demand_id)
        engine.dispose()


def test_postgres_overlapping_path_scopes_serialize_but_independent_scopes_progress() -> None:
    engine = _engine_or_skip()
    with Session(engine) as session:
        demand = _new_demand(session)
        tasks = [
            Task(
                demand_id=demand.id,
                title=title,
                owner_role="backend",
                status="ready",
                path_scopes=[scope],
            )
            for title, scope in (
                ("broad", "apps/registry/**"),
                ("overlap", "apps/registry/api/users.py"),
                ("independent", "apps/factory/main.py"),
            )
        ]
        session.add_all(tasks)
        session.commit()
        demand_id = demand.id
        broad_id, overlap_id, independent_id = (task.id for task in tasks)
    barrier = Barrier(2)

    def claim(worker: str) -> str | None:
        with Session(engine) as session:
            barrier.wait(timeout=5)
            task = claim_task(session, worker, demand_id=demand_id, ttl=timedelta(seconds=20))
            task_id = task.id if task else None
            session.commit()
            return task_id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed = list(pool.map(claim, ("worker-path-a", "worker-path-b")))
        assert set(claimed) == {broad_id, independent_id}
        with Session(engine) as session:
            broad = session.get(Task, broad_id)
            assert broad and broad.lease_owner
            commit_worker_result(
                session,
                broad.id,
                broad.lease_owner,
                broad.fencing_token,
                result={"review": "pending"},
            )
            session.commit()
        with Session(engine) as session:
            next_task = claim_task(
                session, "worker-path-c", demand_id=demand_id, ttl=timedelta(seconds=20)
            )
            assert next_task and next_task.id == overlap_id
            session.commit()
    finally:
        _cleanup(engine, demand_id)
        engine.dispose()


def test_postgres_expired_path_lease_does_not_block_overlapping_claim() -> None:
    engine = _engine_or_skip()
    expired_at = datetime.now(UTC) - timedelta(seconds=2)
    with Session(engine) as session:
        demand = _new_demand(session)
        holder = Task(
            demand_id=demand.id,
            title="Expired path reservation",
            owner_role="backend",
            status="review",
            path_scopes=["apps/registry/**"],
            lease_owner=None,
            lease_expires_at=expired_at,
        )
        waiting = Task(
            demand_id=demand.id,
            title="Task after lease expiry",
            owner_role="backend",
            status="ready",
            path_scopes=["apps/registry/api/users.py"],
        )
        session.add_all([holder, waiting])
        session.flush()
        session.add(
            TaskPathLease(
                task_id=holder.id,
                scope="apps/registry/**",
                expires_at=expired_at,
            )
        )
        session.commit()
        demand_id, waiting_id = demand.id, waiting.id
    try:
        with Session(engine) as session:
            claimed = claim_task(
                session, "worker-after-expiry", demand_id=demand_id,
                ttl=timedelta(seconds=20),
            )
            assert claimed is not None and claimed.id == waiting_id
            session.commit()
    finally:
        _cleanup(engine, demand_id)
        engine.dispose()


def test_postgres_lease_heartbeat_renews_running_and_fences_expired_worker() -> None:
    engine = _engine_or_skip()
    with Session(engine) as session:
        demand = _new_demand(session)
        task = Task(
            demand_id=demand.id,
            title="Synthetic lease lifecycle acceptance",
            owner_role="backend",
            status="ready",
        )
        session.add(task)
        session.commit()
        demand_id, task_id = demand.id, task.id
    try:
        with Session(engine) as session:
            first = claim_task(
                session, "worker-old", demand_id=demand_id, ttl=timedelta(seconds=20)
            )
            assert first and first.id == task_id
            first_token = first.fencing_token
            first.status = "running"
            session.commit()
        with Session(engine) as session:
            renewed = heartbeat(session, task_id, "worker-old", first_token)
            session.commit()
            assert renewed > datetime.now(UTC)
        with Session(engine) as session:
            session.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            session.commit()
        with Session(engine) as session, pytest.raises(LeaseError, match="LEASE_LOST"):
            heartbeat(session, task_id, "worker-old", first_token)
            session.commit()
        with Session(engine) as session:
            second = claim_task(
                session, "worker-new", demand_id=demand_id, ttl=timedelta(seconds=20)
            )
            assert second and second.fencing_token == first_token + 1
            session.commit()
        with Session(engine) as session, pytest.raises(LeaseError, match="LEASE_LOST"):
            commit_worker_result(
                session, task_id, "worker-old", first_token, result={"stale": True}
            )
    finally:
        _cleanup(engine, demand_id)
        engine.dispose()
