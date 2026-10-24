from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from shared_contracts.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from task_engine.audit import render_approved_requirement, snapshot_entity, store_artifact
from task_engine.leases import LeaseError, claim_task, commit_worker_result
from task_engine.models import Demand, EventInbox, EventOutbox, RequirementRevision, Task
from task_engine.outbox import consume_once, enqueue_event, publish_pending
from task_engine.scheduler import run_fake_demand


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db
    engine.dispose()


def _task(
    session: Session, *, demand_id: str | None = None, title: str = "work", role: str = "backend"
) -> Task:
    if demand_id is None:
        demand = Demand(source="manual", external_id=title, title=title, demand_type="feature")
        session.add(demand)
        session.flush()
        demand_id = demand.id
    task = Task(demand_id=demand_id, title=title, owner_role=role, status="ready")
    session.add(task)
    session.flush()
    return task


def test_claim_fencing_and_stale_worker_rejection(session: Session) -> None:
    task = _task(session)
    first = claim_task(session, "worker-a", ttl=timedelta(seconds=1))
    assert first and first.id == task.id and first.fencing_token == 1
    assert claim_task(session, "worker-b") is None
    first.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.flush()
    second = claim_task(session, "worker-b")
    assert second and second.fencing_token == 2
    with pytest.raises(LeaseError, match="LEASE_LOST"):
        commit_worker_result(session, task.id, "worker-a", 1, result={"stale": True})


def test_two_workers_cannot_claim_same_task_concurrently(tmp_path) -> None:
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'claims.db'}", connect_args={"timeout": 5})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        task = _task(db)
        task_id = task.id
    barrier = Barrier(2)

    def attempt(worker: str) -> str | None:
        barrier.wait()
        with factory.begin() as db:
            claimed = claim_task(db, worker)
            return claimed.id if claimed else None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ("worker-a", "worker-b")))
    assert results.count(task_id) == 1
    assert results.count(None) == 1
    engine.dispose()


def test_outbox_inbox_deduplicate_and_publish_after_commit(session: Session) -> None:
    row = enqueue_event(session, "e-1", "task.done", {"task": "t1"})
    assert enqueue_event(session, "e-1", "task.done", {"task": "t1"}).id == row.id
    calls = []
    handled, result = consume_once(session, "e-1", lambda: {"ok": True})
    assert handled and result == {"ok": True}
    assert consume_once(session, "e-1", lambda: {"bad": True}) == (False, {"ok": True})
    session.commit()
    # Use a bound factory so the publisher helper opens independent transactions.
    engine = session.get_bind()
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    assert publish_pending(factory, lambda *args: calls.append(args)) == 1
    assert calls == [("e-1", "task.done", {"task": "t1"})]
    assert session.get(EventInbox, "e-1") is not None
    session.expire_all()
    assert session.get(EventOutbox, row.id).published_at is not None


def test_artifact_allowlist_and_snapshot_hash(session: Session, tmp_path) -> None:
    task = _task(session)
    artifact = store_artifact(
        session,
        tmp_path,
        subject_type="task",
        subject_id=task.id,
        name="result.json",
        content=b'{"ok":true}',
    )
    assert (tmp_path / artifact.relative_path).read_bytes() == b'{"ok":true}'
    assert len(artifact.sha256) == 64
    with pytest.raises(ValueError, match="INVALID_ARTIFACT_PATH"):
        store_artifact(
            session,
            tmp_path,
            subject_type="task",
            subject_id=task.id,
            name="../secret",
            content=b"no",
        )
    snapshot = snapshot_entity(session, task, entity_type="task")
    assert snapshot.content["id"] == task.id and len(snapshot.sha256) == 64
    with pytest.raises(ValueError, match="REQUIREMENT_NOT_APPROVED"):
        render_approved_requirement(
            RequirementRevision(
                demand_id=task.demand_id, version=1, content="x", acceptance=[], decision="proposed"
            )
        )


def test_fake_scheduler_runs_dependency_chain_and_dedupes_events(session: Session) -> None:
    from task_engine.dependencies import add_dependencies

    demand = Demand(source="manual", external_id="fake", title="Fake", demand_type="feature")
    session.add(demand)
    session.flush()
    analyst = _task(session, demand_id=demand.id, title="analysis", role="analyst")
    backend = _task(session, demand_id=demand.id, title="implementation", role="backend")
    qa = _task(session, demand_id=demand.id, title="verification", role="qa")
    add_dependencies(
        session, [analyst.id, backend.id, qa.id], [(backend.id, analyst.id), (qa.id, backend.id)]
    )
    completed = run_fake_demand(session, demand.id)
    assert completed == [analyst.id, backend.id, qa.id]
    assert all(session.get(Task, task_id).status == "done" for task_id in completed)
    assert session.query(EventInbox).count() == 3
    assert all(session.get(Task, task_id).result["model_called"] is False for task_id in completed)
