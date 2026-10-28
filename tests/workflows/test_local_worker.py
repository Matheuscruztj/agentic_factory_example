from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import UTC, datetime

import pytest
from agent_runtime.ollama_adapter import ChatResult, ModelIdentity
from factory_workers.runner import LocalWorker, WorkerConfig
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.execution import ExecutionError, assert_task_authorized, execution_plan
from task_engine.models import (
    AgentRun,
    ApprovalRequest,
    Demand,
    EventOutbox,
    GateEvidence,
    RequirementRevision,
    Task,
)
from task_engine.outbox import enqueue_event


def authorize(session, task):
    plan = execution_plan(session, task.demand_id)
    grant = ApprovalRequest(
        entity_type="demand",
        entity_id=task.demand_id,
        entity_version=1,
        payload_hash="f" * 64,
        requested_by="planner",
        status="approved",
        decision_by="operator",
        decided_at=datetime.now(UTC),
    )
    session.add(grant)
    session.flush()
    enqueue_event(
        session,
        f"approval-decided:{grant.id}",
        "human.approval.decided",
        {
            "approval_id": grant.id,
            "decision": "approved",
            "payload_hash": grant.payload_hash,
            "execution_plan": plan,
        },
    )
    return grant


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "baseline",
        ],
        check=True,
    )
    sha = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
    engine = create_engine(f"sqlite:///{tmp_path / 'state.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        demand = Demand(
            source="manual", external_id="worker", title="Fix value", demand_type="bug", version=1
        )
        session.add(demand)
        session.flush()
        revision = RequirementRevision(
            demand_id=demand.id,
            version=1,
            content="Set value to 2",
            acceptance=["value is 2"],
            decision="approved",
        )
        task = Task(
            demand_id=demand.id,
            title="Fix value",
            owner_role="backend",
            path_scopes=["app.py"],
            acceptance=["value is 2"],
            execution_spec={
                "base_git_sha": sha,
                "profile": "python-fixture",
                "fixture_path": "test_app.py",
                "context_paths": ["app.py"],
            },
        )
        session.add_all([revision, task])
        session.flush()
        task_id = task.id
    cfg = WorkerConfig(
        repo,
        tmp_path / "worktrees",
        tmp_path / "runtime",
        "sha256:" + "a" * 64,
        coding_model="coder",
        review_model="reviewer",
    )
    yield factory, cfg, task_id
    engine.dispose()


class Model:
    def __init__(self):
        self.calls = []

    async def identify(self, tag):
        return ModelIdentity(tag, "1" * 64 if tag == "coder" else "2" * 64, ())

    async def chat(self, tag, messages, **kwargs):
        self.calls.append(tag)
        value = (
            {"files": [{"path": "app.py", "content": "value = 2\n"}]}
            if tag == "coder"
            else {"findings": []}
        )
        if "verdict" in kwargs.get("format_schema", {}).get("properties", {}):
            schema = kwargs["format_schema"]["properties"]
            value = {
                "schema": 1,
                "judge_model": tag,
                "executor_model": schema["executor_model"]["const"],
                "confidence": 0.95,
                "verdict": "pass",
                "rationale": "Gate evidence matches.",
                "evidence_refs": schema["evidence_refs"]["items"]["enum"],
                "human_review_required": False,
            }
        return ChatResult(
            tag, "1" * 64 if tag == "coder" else "2" * 64, (), json.dumps(value), (), 12, 12, 1000
        )


def passing_gate(worktree, name, spec):
    assert (worktree / "app.py").read_text() == "value = 2\n"
    return {"name": name, "status": "pass", "exit_code": 0, "output": "fixture pass"}


def test_worker_rejects_revision_or_plan_without_authorization(setup):
    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        with pytest.raises(ExecutionError, match="PLAN_APPROVAL_REQUIRED"):
            assert_task_authorized(session, task)
        authorize(session, task)
        assert_task_authorized(session, task)
        task.path_scopes = ["other.py"]
        with pytest.raises(ExecutionError, match="PLAN_APPROVAL_REQUIRED"):
            assert_task_authorized(session, task)


def test_proposed_revision_never_creates_a_run(setup):
    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        authorize(session, task)
        revision = session.scalar(select(RequirementRevision))
        revision.decision = "proposed"
    worker = LocalWorker(factory, cfg, adapter=Model(), gate_runner=passing_gate)
    with pytest.raises(ExecutionError, match="REQUIREMENT_NOT_APPROVED"):
        worker.dispatch()
    with factory() as session:
        assert not session.scalars(select(AgentRun)).all()


def test_worker_runs_approved_plan_and_replay_does_not_repeat_effect(setup):
    factory, cfg, task_id = setup
    with factory.begin() as session:
        authorize(session, session.get(Task, task_id))
    model = Model()
    worker = LocalWorker(factory, cfg, adapter=model, gate_runner=passing_gate)
    assert worker.dispatch() == 1
    result = asyncio.run(worker.execute_one())
    assert result["status"] == "done", result
    with factory() as session:
        task = session.get(Task, task_id)
        assert task.status == "done"
        assert task.result["provenance"] == "versioned_local_worker"
        assert len(session.scalars(select(AgentRun)).all()) == 1
        assert len(session.scalars(select(GateEvidence)).all()) == 1
    assert worker.dispatch() == 0
    assert asyncio.run(worker.execute_one())["status"] == "idle"
    assert model.calls == ["coder", "reviewer"]
    assert (cfg.repository / "app.py").read_text() == "value = 1\n"


def test_failed_gate_stops_review_and_completion(setup):
    factory, cfg, task_id = setup
    with factory.begin() as session:
        authorize(session, session.get(Task, task_id))
    model = Model()
    worker = LocalWorker(
        factory,
        cfg,
        adapter=model,
        gate_runner=lambda *_: {
            "status": "fail",
            "exit_code": 1,
            "output": "expected behavior missing",
        },
    )
    worker.dispatch()
    result = asyncio.run(worker.execute_one())
    assert result["status"] == "retry_wait"
    assert model.calls == ["coder"]
    with factory() as session:
        assert session.get(Task, task_id).status == "ready"
        assert session.scalar(select(GateEvidence)).status == "fail"


def test_plan_binds_execution_profile_and_budget(setup):
    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        authorize(session, task)
        task.execution_spec = {**task.execution_spec, "max_attempts": 3}
        with pytest.raises(ExecutionError, match="PLAN_APPROVAL_REQUIRED"):
            assert_task_authorized(session, task)
        event = session.scalar(select(EventOutbox))
        assert (
            event.payload["execution_plan"]["tasks"][0]["execution_spec"].get("max_attempts")
            is None
        )


class PlanningModel(Model):
    def __init__(self, invalid=False):
        super().__init__()
        self.invalid = invalid

    async def chat(self, tag, messages, **kwargs):
        request = json.loads(messages[1]["content"])
        if request["role"] == "analyst":
            output = {
                "facts": [
                    {
                        "path": "app.py",
                        "line": 999 if self.invalid else 1,
                        "fact": "Value is currently one.",
                    }
                ],
                "questions": [],
            }
        else:
            output = {
                "tasks": [
                    {
                        "key": "T1",
                        "title": "Fix value",
                        "role": "backend",
                        "paths": ["app.py"],
                        "acceptance": ["Value equals 2"],
                        "depends_on": [],
                    }
                ]
            }
        return ChatResult(tag, "1" * 64, (), json.dumps(output), (), 12, 12, 1000)


def test_planner_persists_draft_and_replay_does_not_duplicate_tasks(setup):
    from factory_workers.planning import plan_pending
    from task_engine.models import EventInbox

    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        demand_id, spec = task.demand_id, task.execution_spec
        session.delete(task)
        enqueue_event(
            session,
            "plan-request",
            "demand.plan.requested",
            {"demand_id": demand_id, "spec": spec, "request_id": "test-plan"},
        )
    worker = LocalWorker(factory, cfg, adapter=PlanningModel(), gate_runner=passing_gate)
    outcome = asyncio.run(plan_pending(worker))
    assert outcome[0]["status"] == "proposed"
    assert asyncio.run(plan_pending(worker)) == []
    with factory() as session:
        tasks = session.scalars(select(Task)).all()
        assert len(tasks) == 1 and tasks[0].status == "proposed"
        assert tasks[0].execution_spec == spec
        assert session.get(EventInbox, "plan-request") is not None
        with pytest.raises(ExecutionError, match="PLAN_APPROVAL_REQUIRED"):
            assert_task_authorized(session, tasks[0])


def test_discovery_requires_real_line_and_has_finite_retries(setup):
    from factory_workers.planning import plan_pending
    from task_engine.models import EventInbox

    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        enqueue_event(
            session,
            "discovery-request",
            "demand.discovery.requested",
            {"demand_id": task.demand_id, "spec": task.execution_spec, "request_id": "discovery"},
        )
    worker = LocalWorker(
        factory, cfg, adapter=PlanningModel(invalid=True), gate_runner=passing_gate
    )
    assert asyncio.run(plan_pending(worker))[0]["status"] == "retry_wait"
    assert asyncio.run(plan_pending(worker))[0]["status"] == "blocked"
    assert asyncio.run(plan_pending(worker)) == []
    with factory() as session:
        inbox = session.get(EventInbox, "discovery-request")
        assert inbox.result["code"] == "DISCOVERY_GROUNDING_REQUIRED"
        assert session.get(Task, task_id).status == "proposed"
        assert not session.scalars(select(AgentRun)).all()


def test_failed_code_repairs_stop_at_attempt_budget(setup):
    factory, cfg, task_id = setup
    with factory.begin() as session:
        authorize(session, session.get(Task, task_id))
    model = Model()
    worker = LocalWorker(
        factory,
        cfg,
        adapter=model,
        gate_runner=lambda *_: {"status": "fail", "exit_code": 1, "output": "Behavior still wrong"},
    )
    worker.dispatch()
    assert asyncio.run(worker.execute_one())["status"] == "retry_wait"
    assert asyncio.run(worker.execute_one())["status"] == "blocked"
    assert asyncio.run(worker.execute_one())["status"] == "idle"
    assert model.calls == ["coder", "coder"]
    with factory() as session:
        assert session.get(Task, task_id).status == "blocked"
        assert len(session.scalars(select(AgentRun)).all()) == 2


@pytest.mark.parametrize("tamper", ["gate_sha", "gate_status", "review_sha", "run_attempt"])
def test_completion_rejects_forged_or_stale_proof(setup, tamper):
    from task_engine.transitions import TransitionError, apply_transition

    factory, cfg, task_id = setup
    with factory.begin() as session:
        authorize(session, session.get(Task, task_id))
    worker = LocalWorker(factory, cfg, adapter=Model(), gate_runner=passing_gate)
    worker.dispatch()
    assert asyncio.run(worker.execute_one())["status"] == "done"
    with factory.begin() as session:
        task = session.get(Task, task_id)
        task.status = "review"
        gate = session.scalar(select(GateEvidence))
        if tamper == "gate_sha":
            gate.git_sha = "0" * 40
        elif tamper == "gate_status":
            gate.status = "fail"
        elif tamper == "review_sha":
            task.result = {**task.result, "reviewed_sha": "0" * 40}
        else:
            task.result = {**task.result, "attempt": 99}
        session.flush()
        with pytest.raises(TransitionError, match="COMPLETION"):
            apply_transition(
                session,
                task,
                entity_type="task",
                new_state="done",
                expected_version=task.state_version,
                actor="forged-result",
                reason="Try to complete with wrong evidence",
                idempotency_key="forged",
            )


@pytest.mark.parametrize("tamper", [False, True])
def test_assisted_patch_is_hash_bound_and_never_claims_local_generation(setup, tamper):
    import hashlib

    factory, cfg, task_id = setup
    folder = cfg.runtime_root / "artifacts/approved-patches"
    folder.mkdir(parents=True)
    bundle = folder / "fix.json"
    bundle.write_text(
        json.dumps(
            {
                "executor_kind": "assisted_patch",
                "author": "codex-assisted",
                "files": [{"path": "app.py", "content": "value = 2\n"}],
            }
        )
    )
    with factory.begin() as session:
        task = session.get(Task, task_id)
        task.execution_spec = {
            **task.execution_spec,
            "executor": "assisted_patch",
            "patch_artifact": "artifacts/approved-patches/fix.json",
            "patch_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        }
        authorize(session, task)
    if tamper:
        bundle.write_text(bundle.read_text() + "\n")
    model = Model()
    worker = LocalWorker(factory, cfg, adapter=model, gate_runner=passing_gate)
    worker.dispatch()
    result = asyncio.run(worker.execute_one())
    assert result["status"] == ("blocked" if tamper else "done"), result
    with factory() as session:
        run = session.scalar(select(AgentRun))
        if tamper:
            assert run is None
            assert model.calls == []
        else:
            assert run.executor_kind == "assisted_patch"
            assert run.model_id == "codex-assisted"
            assert run.model_digest is None
            assert model.calls == ["reviewer"]


def test_scoped_dispatch_leaves_other_demand_approval_unconsumed(setup):
    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        demand_id = task.demand_id
        authorize(session, task)
    worker = LocalWorker(factory, cfg, adapter=Model(), gate_runner=passing_gate)
    assert worker.dispatch(demand_id="unrelated-demand") == 0
    with factory() as session:
        assert session.get(Task, task_id).status == "proposed"
        assert session.scalar(select(EventOutbox)).published_at is None
    assert worker.dispatch(demand_id=demand_id) == 1


def test_dispatch_retires_stale_plan_grant_before_authorized_replacement(setup):
    from task_engine.models import EventInbox

    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        demand_id = task.demand_id
        authorize(session, task)
        task.execution_spec = {**task.execution_spec, "max_attempts": 3}
    worker = LocalWorker(factory, cfg, adapter=Model(), gate_runner=passing_gate)
    assert worker.dispatch(demand_id=demand_id) == 0
    with factory.begin() as session:
        event = session.scalar(
            select(EventOutbox).where(EventOutbox.event_type == "human.approval.decided")
        )
        inbox = session.get(EventInbox, "executor:" + event.event_id)
        assert inbox.result["status"] == "stale_plan"
        assert event.published_at is not None
        authorize(session, session.get(Task, task_id))
    assert worker.dispatch(demand_id=demand_id) == 1


def test_scoped_planning_filters_before_limit_and_preserves_other_events(setup):
    from factory_workers.planning import plan_pending

    factory, cfg, task_id = setup
    with factory.begin() as session:
        task = session.get(Task, task_id)
        demand_id, spec = task.demand_id, task.execution_spec
        enqueue_event(
            session,
            "unrelated-request",
            "demand.discovery.requested",
            {"demand_id": "unrelated-demand", "spec": spec, "request_id": "unrelated"},
        )
        enqueue_event(
            session,
            "selected-request",
            "demand.discovery.requested",
            {"demand_id": demand_id, "spec": spec, "request_id": "selected"},
        )
    worker = LocalWorker(factory, cfg, adapter=PlanningModel(), gate_runner=passing_gate)
    result = asyncio.run(plan_pending(worker, demand_id=demand_id, limit=1))
    assert len(result) == 1 and result[0]["status"] == "grounded"
    assert result[0]["event_id"] == "selected-request"
    with factory() as session:
        unrelated = session.scalar(
            select(EventOutbox).where(EventOutbox.event_id == "unrelated-request")
        )
        assert unrelated.published_at is None and unrelated.attempts == 0
    assert asyncio.run(plan_pending(worker, demand_id=demand_id)) == []


@pytest.mark.parametrize(
    "planning_status,expected", [("blocked", 1), ("retry_wait", 1), ("grounded", 0)]
)
def test_worker_once_reports_planning_failure_and_scopes_every_stage(
    monkeypatch, tmp_path, planning_status, expected
):
    from types import SimpleNamespace

    from factory_workers import planning

    from scripts import factory_worker

    seen = []

    class Worker:
        def __init__(self, *_):
            pass

        def dispatch(self, *, demand_id):
            seen.append(("dispatch", demand_id))
            return 0

        async def execute_one(self, *, demand_id):
            seen.append(("execute", demand_id))
            return {"status": "idle"}

    async def plan(_worker, *, demand_id):
        seen.append(("plan", demand_id))
        return [{"status": planning_status}]

    monkeypatch.setattr(factory_worker, "LocalWorker", Worker)
    monkeypatch.setattr(
        factory_worker, "create_engine", lambda *a, **k: SimpleNamespace(dispose=lambda: None)
    )
    monkeypatch.setattr(factory_worker, "sessionmaker", lambda **k: None)
    monkeypatch.setattr(factory_worker.signal, "signal", lambda *a: None)
    monkeypatch.setattr(planning, "plan_pending", plan)
    args = SimpleNamespace(
        demand_id="selected",
        once=True,
        worktree_root=tmp_path,
        sandbox_image="sha256:test",
        worker_id="test",
        interval=1,
    )
    assert asyncio.run(factory_worker.run(args, {"DATABASE_URL": "unused"})) == expected
    assert seen == [("plan", "selected"), ("dispatch", "selected"), ("execute", "selected")]
