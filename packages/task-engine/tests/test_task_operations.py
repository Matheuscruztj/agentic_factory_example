from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from shared_contracts.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from task_engine.audit import render_approved_requirement, snapshot_entity, store_artifact
from task_engine.execution import execution_plan
from task_engine.leases import LeaseError, claim_task, commit_worker_result
from task_engine.models import (
    ApprovalRequest,
    Demand,
    EventInbox,
    EventOutbox,
    RequirementRevision,
    Task,
    TaskPathLease,
)
from task_engine.outbox import consume_once, enqueue_event, publish_pending
from task_engine.runs import RunProvenanceError, create_run, record_gate
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


def test_priority_aging_prevents_old_work_from_being_starved(session: Session) -> None:
    from task_engine.leases import PRIORITY_AGING_AFTER

    now = datetime.now(UTC)
    aged = _task(session, title="aged-low-priority")
    urgent = _task(session, title="fresh-high-priority")
    aged.priority = 0
    aged.created_at = now - PRIORITY_AGING_AFTER - timedelta(seconds=1)
    urgent.priority = 100
    urgent.created_at = now
    session.flush()

    claimed = claim_task(session, "fair-worker")

    assert claimed is not None and claimed.id == aged.id


def test_path_leases_serialize_overlaps_and_allow_independent_scopes(session: Session) -> None:
    broad = _task(session, title="broad")
    broad.path_scopes = ["apps/customer-registry/**"]
    overlapping = _task(session, title="overlap")
    overlapping.path_scopes = ["apps/customer-registry/api/src/users.py"]
    independent = _task(session, title="independent")
    independent.path_scopes = ["apps/factory-api/src/main.py"]
    session.flush()

    first = claim_task(session, "worker-a")
    second = claim_task(session, "worker-b")

    assert first is not None and first.id == broad.id
    assert second is not None and second.id == independent.id
    assert claim_task(session, "worker-c") is None

    commit_worker_result(session, broad.id, "worker-a", first.fencing_token, result={"ok": True})
    third = claim_task(session, "worker-c")
    assert third is not None and third.id == overlapping.id


def test_path_lease_heartbeat_renews_scope_and_rejects_unsafe_paths(session: Session) -> None:
    from task_engine.leases import heartbeat

    task = _task(session, title="scoped")
    task.path_scopes = ["apps/factory-api/**"]
    session.flush()
    claimed = claim_task(session, "worker", ttl=timedelta(seconds=10))
    assert claimed is not None

    expiry = heartbeat(session, task.id, "worker", claimed.fencing_token, ttl=timedelta(minutes=1))
    lease = session.query(TaskPathLease).filter_by(task_id=task.id).one()
    assert lease.expires_at.replace(tzinfo=UTC) == expiry

    unsafe = _task(session, title="unsafe")
    unsafe.path_scopes = ["../../.env"]
    session.flush()
    with pytest.raises(LeaseError, match="INVALID_PATH_SCOPE"):
        claim_task(session, "worker-two")
    unsafe.path_scopes = ["apps/*/unsupported-middle-glob.py"]
    session.flush()
    with pytest.raises(LeaseError, match="INVALID_PATH_SCOPE"):
        claim_task(session, "worker-three")


def test_path_scope_globs_allow_only_terminal_directory_wildcards(session: Session) -> None:
    from task_engine.leases import _validated_scopes

    assert _validated_scopes(["apps/registry/*"]) == ("apps/registry/*",)
    assert _validated_scopes(["apps/registry/**"]) == ("apps/registry/**",)
    for scope in (
        "apps/**/users.py",
        "apps/re*gistry/users.py",
        "apps/registry/?/users.py",
        "**",
    ):
        with pytest.raises(LeaseError, match="INVALID_PATH_SCOPE"):
            _validated_scopes([scope])


def test_single_level_path_scope_overlaps_one_child_only() -> None:
    from task_engine.leases import _scope_overlaps

    assert _scope_overlaps("apps/registry/*", "apps/registry/users.py")
    assert not _scope_overlaps("apps/registry/*", "apps/registry/api/users.py")


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
    reviewed = run_fake_demand(session, demand.id)
    assert reviewed == [analyst.id]
    assert session.get(Task, analyst.id).status == "review"
    assert session.get(Task, backend.id).status == "ready"
    assert session.get(Task, qa.id).status == "ready"
    assert session.query(EventInbox).count() == 1
    assert session.get(Task, analyst.id).result["model_called"] is False


def test_run_and_gate_provenance_rejects_mismatched_snapshot(session: Session) -> None:
    task = _task(session)
    task.path_scopes = ["src/**"]
    task.acceptance = ["Checks bind to the tested snapshot."]
    task.execution_spec = {
        "base_git_sha": "d" * 40,
        "profile": "python-fixture",
        "fixture_path": "tests",
        "context_paths": ["src/app.py"],
    }
    revision = RequirementRevision(
        demand_id=task.demand_id,
        version=1,
        content="requirement",
        acceptance=[],
        decision="approved",
    )
    session.add(revision)
    session.flush()
    approval = ApprovalRequest(
        entity_type="demand",
        entity_id=task.demand_id,
        entity_version=1,
        payload_hash="a" * 64,
        requested_by="planner",
        status="approved",
        decision_by="operator",
        decided_at=datetime.now(UTC),
    )
    session.add(approval)
    session.flush()
    enqueue_event(
        session,
        f"approval-decided:{approval.id}",
        "human.approval.decided",
        {
            "approval_id": approval.id,
            "decision": "approved",
            "payload_hash": approval.payload_hash,
            "execution_plan": execution_plan(session, task.demand_id),
        },
    )
    run = create_run(
        session,
        task_id=task.id,
        attempt=1,
        model_id="local-coder",
        model_digest="sha256:model",
        prompt_hash="a" * 64,
        context_hash="b" * 64,
        skill_hash="c" * 64,
        requirement_revision_id=revision.id,
        base_git_sha="d" * 40,
    )
    run.result_git_sha = "e" * 40
    run.tree_hash = "f" * 64
    evidence = record_gate(
        session,
        run_id=run.id,
        check_name="unit",
        status="pass",
        git_sha="e" * 40,
        tree_hash="f" * 64,
        suite_hash="1" * 64,
        tool_hash="2" * 64,
        config_hash="3" * 64,
        artifact_sha256="4" * 64,
    )
    assert evidence.task_id == task.id and evidence.attempt == 1
    with pytest.raises(RunProvenanceError, match="GATE_SHA_MISMATCH"):
        record_gate(
            session,
            run_id=run.id,
            check_name="wrong",
            status="pass",
            git_sha="d" * 40,
            tree_hash="f" * 64,
            suite_hash="1" * 64,
            tool_hash="2" * 64,
            config_hash="3" * 64,
            artifact_sha256="4" * 64,
        )
    with pytest.raises(RunProvenanceError, match="RUN_ATTEMPT_EXISTS"):
        create_run(
            session,
            task_id=task.id,
            attempt=1,
            model_id="local-coder",
            model_digest="sha256:model",
            prompt_hash="a" * 64,
            context_hash="b" * 64,
            skill_hash="c" * 64,
            requirement_revision_id=revision.id,
            base_git_sha="d" * 40,
        )
