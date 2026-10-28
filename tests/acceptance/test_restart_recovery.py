from datetime import UTC, datetime

import pytest
from factory_workers.retry_queue import claim_due_retries, complete_retry, schedule_failure
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.leases import LeaseError, claim_task, commit_worker_result
from task_engine.models import Demand, RetryQueueEntry, Task


def test_restart_retry_queue_recovers_once_and_duplicate_event_keeps_one_identity(tmp_path):
    database = f"sqlite:///{tmp_path / 'recovery.db'}"
    now = datetime(2026, 10, 24, 12, tzinfo=UTC)
    engine = create_engine(database)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        first = schedule_failure(
            session, task_id="task-restart", operation_key="event:duplicate-1",
            attempt=1, max_attempts=3, failure_kind="llm_transient", now=now,
        )
        duplicate = schedule_failure(
            session, task_id="task-restart", operation_key="event:duplicate-1",
            attempt=1, max_attempts=3, failure_kind="llm_transient", now=now,
        )
        assert first.id == duplicate.id
        key_before_restart = first.idempotency_key
    engine.dispose()

    recovered_engine = create_engine(database)
    recovered_factory = sessionmaker(bind=recovered_engine, expire_on_commit=False)
    with recovered_factory.begin() as session:
        rows = claim_due_retries(
            session, now=now.replace(second=5), worker_id="worker-after-restart", limit=10
        )
        assert len(rows) == 1
        assert rows[0].idempotency_key == key_before_restart
        complete_retry(rows[0], worker_id="worker-after-restart", now=now.replace(second=6))
    with recovered_factory() as session:
        stored = session.scalars(select(RetryQueueEntry)).all()
        assert len(stored) == 1
        assert stored[0].status == "completed"
    recovered_engine.dispose()


def test_restarted_worker_fences_stale_process_after_lease_reclaim(tmp_path):
    database = f"sqlite:///{tmp_path / 'fencing.db'}"
    engine = create_engine(database)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        demand = Demand(
            source="manual", external_id="fencing-fixture", title="Fencing fixture",
            demand_type="feature", status="executing",
        )
        session.add(demand)
        session.flush()
        task = Task(
            demand_id=demand.id, title="Recover after worker crash", owner_role="backend",
            status="ready", path_scopes=["src/**"], acceptance=[], risk="normal",
        )
        session.add(task)
        session.flush()
        task_id = task.id

    with factory.begin() as session:
        first = claim_task(session, "worker-before-restart")
        assert first is not None and first.id == task_id
        old_token = first.fencing_token
        first.lease_expires_at = datetime(2000, 1, 1, tzinfo=UTC)

    # Model a new worker process opening the same durable database after restart.
    engine.dispose()
    recovered_engine = create_engine(database)
    recovered_factory = sessionmaker(bind=recovered_engine, expire_on_commit=False)
    with recovered_factory.begin() as session:
        second = claim_task(session, "worker-after-restart")
        assert second is not None and second.id == task_id
        assert second.fencing_token == old_token + 1
        new_token = second.fencing_token

    with recovered_factory.begin() as session:
        with pytest.raises(LeaseError, match="LEASE_LOST"):
            commit_worker_result(
                session, task_id, "worker-before-restart", old_token,
                result={"stale": True},
            )
    with recovered_factory.begin() as session:
        commit_worker_result(
            session, task_id, "worker-after-restart", new_token,
            result={"accepted": True},
        )
    with recovered_factory() as session:
        stored = session.get(Task, task_id)
        assert stored is not None
        assert stored.status == "review"
        assert stored.result == {"accepted": True}
        assert stored.fencing_token == old_token + 1
    recovered_engine.dispose()
