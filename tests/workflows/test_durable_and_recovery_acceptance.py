import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TypedDict

import pytest
from agent_runtime.llm_queue import inference_slot
from agent_runtime.workflows.hitl import require_human_decision, resume_config
from agent_runtime.workflows.proposal_graph import follow_up
from factory_workers.reconciler import reconcile_expired_task_leases
from factory_workers.retries import plan_retry
from factory_workers.retry_queue import (
    RetryableOperationError,
    claim_due_retries,
    complete_retry,
    run_retry_batch,
    schedule_failure,
)
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


def test_approved_proposal_reuses_snapshot_without_restarting_discovery() -> None:
    created = []
    invoked = []
    proposal = {
        "id": "proposal-1",
        "payload_hash": "b" * 64,
        "snapshot_sha": "a" * 40,
    }
    approval = {
        "status": "approved",
        "proposal_id": "proposal-1",
        "payload_hash": "b" * 64,
    }
    result = follow_up(
        proposal,
        approval=approval,
        create_task=lambda item: created.append(item) or "task-1",
        invoke_subworkflow=lambda task, context: invoked.append((task, context)) or "run-1",
    )
    assert result == "run-1" and created == [proposal]
    assert invoked == [("task-1", {"snapshot_sha": "a" * 40, "discovery": "reuse"})]
    with pytest.raises(PermissionError, match="HUMAN_APPROVAL_REQUIRED"):
        follow_up(
            proposal,
            approval={**approval, "status": "pending"},
            create_task=lambda _item: pytest.fail("task created before approval"),
            invoke_subworkflow=lambda *_args: pytest.fail("workflow invoked before approval"),
        )


def test_structured_proposal_requires_scoped_task_before_subworkflow():
    proposal = {
        "id": "proposal-scoped",
        "payload_hash": "c" * 64,
        "snapshot_sha": "a" * 40,
        "proposed_task": {
            "depends_on": [],
            "path_scopes": ["tests/**"],
            "risk": "normal",
        },
    }
    approval = {
        "status": "approved",
        "proposal_id": proposal["id"],
        "payload_hash": proposal["payload_hash"],
    }
    assert (
        follow_up(
            proposal,
            approval=approval,
            create_task=lambda _item: "task-scoped",
            invoke_subworkflow=lambda _task, context: context,
            validate_scope=lambda task: task["path_scopes"] == ["tests/**"],
        )["discovery"]
        == "reuse"
    )
    with pytest.raises(PermissionError, match="PROPOSAL_SCOPE_NOT_ALLOWED"):
        follow_up(
            proposal,
            approval=approval,
            create_task=lambda _item: "task-scoped",
            invoke_subworkflow=lambda *_args: pytest.fail("disallowed scope must not run"),
            validate_scope=lambda _task: False,
        )


def test_retry_policy_caps_backoff_and_dead_letters_exhausted_attempts() -> None:
    now = __import__("datetime").datetime(2026, 10, 24, tzinfo=__import__("datetime").UTC)
    first = plan_retry(task_id="t1", operation_key="ollama:run", attempt=1, max_attempts=3, now=now)
    assert first.state == "retry_wait" and first.available_at == now.replace(second=5)
    last = plan_retry(task_id="t1", operation_key="ollama:run", attempt=3, max_attempts=3, now=now)
    assert last.state == "dead_letter" and last.available_at is None
    assert first.idempotency_key == last.idempotency_key


def test_retry_queue_persists_idempotently_and_only_claims_due_items(tmp_path):
    from shared_contracts.db import Base
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from task_engine.models import RetryQueueEntry

    engine = create_engine(f"sqlite:///{tmp_path / 'retries.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = __import__("datetime").datetime(2026, 10, 24, tzinfo=__import__("datetime").UTC)
    with factory() as session:
        row = schedule_failure(
            session,
            task_id="task-1",
            operation_key="llm:1",
            attempt=1,
            max_attempts=3,
            failure_kind="llm_transient",
            now=now,
        )
        replay = schedule_failure(
            session,
            task_id="task-1",
            operation_key="llm:1",
            attempt=1,
            max_attempts=3,
            failure_kind="llm_transient",
            now=now,
        )
        assert replay.id == row.id
        assert claim_due_retries(session, now=now, worker_id="worker-1", limit=5) == []
        due = claim_due_retries(session, now=now.replace(second=5), worker_id="worker-1", limit=5)
        assert [item.id for item in due] == [row.id]
        complete_retry(row, worker_id="worker-1", now=now.replace(second=6))
        session.commit()
        assert (
            claim_due_retries(session, now=now.replace(second=10), worker_id="worker-2", limit=5)
            == []
        )
        assert len(session.scalars(select(RetryQueueEntry)).all()) == 1
    engine.dispose()


def test_retry_worker_reschedules_transient_failure_then_completes(tmp_path):
    from shared_contracts.db import Base
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from task_engine.models import RetryQueueEntry

    engine = create_engine(f"sqlite:///{tmp_path / 'retry-worker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = __import__("datetime").datetime(2026, 10, 24, tzinfo=__import__("datetime").UTC)
    with factory.begin() as session:
        schedule_failure(
            session,
            task_id="task-1",
            operation_key="operation",
            attempt=1,
            max_attempts=3,
            failure_kind="llm_transient",
            now=now,
        )
    attempts = []

    def fail_once(task_id, key):
        attempts.append((task_id, key))
        if len(attempts) == 1:
            raise RetryableOperationError("llm_transient")

    first = run_retry_batch(
        factory, worker_id="worker-a", now=now.replace(second=5), execute=fail_once
    )
    second = run_retry_batch(
        factory, worker_id="worker-b", now=now.replace(second=15), execute=fail_once
    )
    with factory() as session:
        states = sorted(row.status for row in session.scalars(select(RetryQueueEntry)).all())
    assert first["retry_scheduled"] == 1 and second["completed"] == 1
    assert attempts[0][1] == attempts[1][1]
    assert states == ["completed", "completed"]
    engine.dispose()


def test_reconciler_retries_expired_run_but_never_replays_committed_effect(tmp_path):
    from shared_contracts.db import Base
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from task_engine.models import Demand, RetryQueueEntry, Task, TransitionEvent

    engine = create_engine(f"sqlite:///{tmp_path / 'reconcile.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = __import__("datetime").datetime(2026, 10, 24, 12, tzinfo=__import__("datetime").UTC)
    with factory.begin() as session:
        demand = Demand(
            source="manual",
            external_id="reconcile",
            title="reconcile",
            demand_type="feature",
            status="executing",
        )
        session.add(demand)
        session.flush()
        session.add_all(
            [
                Task(
                    demand_id=demand.id,
                    title="retry me",
                    owner_role="backend",
                    status="running",
                    lease_expires_at=now,
                    lease_owner="dead-worker",
                    fencing_token=1,
                    state_version=1,
                ),
                Task(
                    demand_id=demand.id,
                    title="review me",
                    owner_role="backend",
                    status="running",
                    lease_expires_at=now,
                    lease_owner="dead-worker",
                    fencing_token=2,
                    state_version=1,
                    result={"side_effect_committed": True},
                ),
            ]
        )
    with factory.begin() as session:
        result = reconcile_expired_task_leases(session, now=now)
        assert result == {
            "examined": 2,
            "retry_scheduled": 1,
            "dead_lettered": 0,
            "moved_to_review": 1,
        }
    with factory() as session:
        tasks = {row.title: row.status for row in session.scalars(select(Task)).all()}
        queue = session.scalars(select(RetryQueueEntry)).all()
        events = session.scalars(select(TransitionEvent)).all()
        assert tasks == {"retry me": "retry_wait", "review me": "review"}
        assert len(queue) == 1 and queue[0].status == "retry_wait"
        assert len(events) == 2
    engine.dispose()


def test_postgres_checkpointer_persists_human_pause_across_reopen() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for durable restart acceptance")
    from agent_runtime.langgraph_adapter import compile_durable, postgres_checkpointer

    class ApprovalState(TypedDict, total=False):
        run_id: str
        decision: dict

    run_id = f"acceptance-{uuid.uuid4()}"
    config = resume_config(run_id)
    builder = StateGraph(ApprovalState)

    def approval_node(state):
        request = {
            "run_id": state["run_id"],
            "approval_id": "approval-fixture",
            "entity_type": "task",
            "entity_id": "task-fixture",
            "entity_version": 4,
            "payload_hash": "a" * 64,
        }
        return {
            "decision": require_human_decision(
                request,
                approval_lookup=lambda approval_id: {
                    "id": approval_id,
                    "entity_type": "task",
                    "entity_id": "task-fixture",
                    "entity_version": 4,
                    "payload_hash": "a" * 64,
                    "status": "approved",
                    "decision_by": "acceptance-operator",
                    "requested_by": "agent",
                },
            )
        }

    builder.add_node("approval", approval_node)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    try:
        with postgres_checkpointer(database_url) as saver:
            graph = compile_durable(builder, saver)
            paused = graph.invoke({"run_id": run_id}, config)
            assert "__interrupt__" in paused
        with postgres_checkpointer(database_url) as saver:
            resumed = compile_durable(builder, saver).invoke(
                Command(
                    resume={
                        "decision": "approved",
                        "actor": "acceptance-operator",
                        "approval_id": "approval-fixture",
                    }
                ),
                config,
            )
            assert resumed["decision"]["decision"] == "approved"
    finally:
        with postgres_checkpointer(database_url) as saver:
            saver.delete_thread(run_id)


def test_postgres_checkpointer_resumes_after_worker_process_is_killed(tmp_path: Path) -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for process-restart acceptance")
    from agent_runtime.langgraph_adapter import postgres_checkpointer

    run_id = f"process-restart-{uuid.uuid4()}"
    ready_file = tmp_path / "paused.json"
    script = r'''
import json, os, time
from pathlib import Path
from typing import TypedDict
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from agent_runtime.langgraph_adapter import compile_durable, postgres_checkpointer
from agent_runtime.workflows.hitl import require_human_decision, resume_config

class ApprovalState(TypedDict, total=False):
    run_id: str
    decision: dict

approval_id = "approval-process-restart"
run_id = os.environ["FAC137_RUN_ID"]
config = resume_config(run_id)
request = {
    "run_id": run_id,
    "approval_id": approval_id,
    "entity_type": "task",
    "entity_id": "task-process-restart",
    "entity_version": 4,
    "payload_hash": "a" * 64,
}
approval = {
    "id": approval_id,
    "entity_type": "task",
    "entity_id": "task-process-restart",
    "entity_version": 4,
    "payload_hash": "a" * 64,
    "status": "approved",
    "decision_by": "acceptance-operator",
    "requested_by": "agent",
}
def gate(state):
    return {"decision": require_human_decision(
        request, approval_lookup=lambda _approval_id: approval
    )}
builder = StateGraph(ApprovalState)
builder.add_node("approval", gate)
builder.add_edge(START, "approval")
builder.add_edge("approval", END)
try:
    with postgres_checkpointer() as saver:
        graph = compile_durable(builder, saver)
        if os.environ["FAC137_MODE"] == "pause":
            paused = graph.invoke({"run_id": run_id}, config)
            Path(os.environ["FAC137_READY_FILE"]).write_text(
                json.dumps({"interrupts": len(paused.get("__interrupt__", []))})
            )
            time.sleep(120)
        else:
            result = graph.invoke(Command(resume={
                "decision": "approved",
                "actor": "acceptance-operator",
                "approval_id": approval_id,
            }), config)
            print(json.dumps({"decision": result["decision"]["decision"],
                              "actor": result["decision"]["actor"]}))
finally:
    if os.environ["FAC137_MODE"] == "resume":
        with postgres_checkpointer() as saver:
            saver.delete_thread(run_id)
'''
    env = {
        **os.environ,
        "FAC137_RUN_ID": run_id,
        "FAC137_READY_FILE": str(ready_file),
        "FAC137_MODE": "pause",
    }
    worker = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not ready_file.exists():
            if worker.poll() is not None:
                break
            time.sleep(0.1)
        assert ready_file.exists(), "worker did not persist the PostgreSQL HITL checkpoint"
        assert __import__("json").loads(ready_file.read_text())["interrupts"] == 1
        worker.terminate()
        worker.wait(timeout=10)

        resume_env = {**env, "FAC137_MODE": "resume"}
        resumed = subprocess.run(
            [sys.executable, "-c", script],
            env=resume_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
            check=False,
        )
        assert resumed.returncode == 0, "new worker failed to resume the persisted HITL state"
        assert resumed.stdout.strip() == '{"decision": "approved", "actor": "acceptance-operator"}'
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait(timeout=10)
        if not ready_file.exists():
            with postgres_checkpointer(database_url) as saver:
                saver.delete_thread(run_id)


def test_postgres_inference_slots_bound_concurrent_runs() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for cross-process lock acceptance")
    import psycopg

    def second_worker() -> str:
        with psycopg.connect(_psycopg_url(database_url)) as connection:
            with inference_slot(connection, max_parallel=1, timeout_seconds=0.3):
                return "entered"

    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(_psycopg_url(database_url)) as connection:
            with inference_slot(connection, max_parallel=1, timeout_seconds=1):
                future = pool.submit(second_worker)
                assert not future.done()
        assert future.result(timeout=2) == "entered"


def _psycopg_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)
