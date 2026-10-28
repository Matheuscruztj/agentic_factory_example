from agent_runtime.workflows.fakes import FakeModel, FakeTools
from agent_runtime.workflows.hitl import require_human_decision
from agent_runtime.workflows.task_graph import build_task_graph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


def test_graph_runner_uses_only_local_fakes() -> None:
    model = FakeModel(["plan", "result"])
    tools = FakeTools({"read": lambda path: f"read:{path}"})

    def execute(state):
        plan = model.invoke(state["task_id"])
        result = tools.invoke("read", path=plan)
        return {"execution_ok": True, "check_exit_code": 0, "result": result}

    graph = build_task_graph(
        preflight=lambda _state: {"preflight_ok": True},
        policy=lambda _state: {"policy_ok": True},
        context=lambda _state: {"context_ready": True},
        execute=execute,
        verify=lambda state: {"check_exit_code": state.get("check_exit_code", 2)},
        compensate=lambda _state: {"status": "failed"},
    ).compile()
    result = graph.invoke({"task_id": "local-fixture", "retry_count": 0, "retry_limit": 0})
    assert result["status"] == "done"
    assert model.calls == 1
    assert tools.calls == [("read", {"path": "plan"})]


def test_nonzero_check_never_marks_task_done() -> None:
    graph = build_task_graph(
        preflight=lambda _state: {"preflight_ok": True},
        policy=lambda _state: {"policy_ok": True},
        context=lambda _state: {"context_ready": True},
        execute=lambda _state: {"execution_ok": True},
        verify=lambda _state: {"check_exit_code": 2},
        compensate=lambda _state: {"status": "failed"},
    ).compile()
    result = graph.invoke({"task_id": "local-failure", "retry_count": 0, "retry_limit": 0})
    assert result["status"] == "failed"


def test_graph_preserves_provenance_payload_between_operational_nodes() -> None:
    observed = {}

    def preflight(_state):
        return {
            "preflight_ok": True,
            "base_sha": "a" * 40,
            "requirement_revision_id": "revision-1",
            "model_id": "qwen2.5-coder:7b",
            "model_digest": "model-digest",
        }

    def policy(state):
        observed["policy"] = (state["base_sha"], state["requirement_revision_id"])
        return {"policy_ok": True, "run_id": "run-1", "allowed_paths": ["src/app.py"]}

    def context(state):
        observed["context"] = (state["run_id"], state["allowed_paths"])
        return {"context_ready": True, "context_sha256": "b" * 64}

    graph = build_task_graph(
        preflight=preflight,
        policy=policy,
        context=context,
        execute=lambda _state: {"execution_ok": True},
        verify=lambda _state: {"check_exit_code": 0},
        compensate=lambda _state: {"status": "failed"},
    ).compile()

    result = graph.invoke({"task_id": "provenance-fixture", "retry_count": 0, "retry_limit": 0})

    assert result["status"] == "done"
    assert result["model_digest"] == "model-digest"
    assert result["context_sha256"] == "b" * 64
    assert observed == {
        "policy": ("a" * 40, "revision-1"),
        "context": ("run-1", ["src/app.py"]),
    }


def _approval_graph(approval):
    graph = StateGraph(dict)

    def resume(state):
        request = {
            "approval_id": "approval-1",
            "entity_type": "task",
            "entity_id": "task-1",
            "entity_version": 3,
            "payload_hash": "a" * 64,
        }
        return {
            "decision": require_human_decision(
                request, approval_lookup=lambda _approval_id: approval
            )
        }

    graph.add_node("approval", resume)
    graph.add_edge(START, "approval")
    graph.add_edge("approval", END)
    return graph.compile(checkpointer=MemorySaver())


def test_human_resume_requires_matching_persisted_approval() -> None:
    config = {"configurable": {"thread_id": "approval-thread"}}
    approval = {
        "id": "approval-1",
        "entity_type": "task",
        "entity_id": "task-1",
        "entity_version": 3,
        "payload_hash": "a" * 64,
        "status": "approved",
        "decision_by": "operator",
        "requested_by": "agent",
    }
    graph = _approval_graph(approval)
    assert "__interrupt__" in graph.invoke({}, config)
    result = graph.invoke(
        Command(
            resume={
                "decision": "approved",
                "actor": "operator",
                "approval_id": "approval-1",
            }
        ),
        config,
    )
    assert result["decision"]["actor"] == "operator"


def test_human_resume_rejects_stale_persisted_approval() -> None:
    config = {"configurable": {"thread_id": "approval-thread-stale"}}
    approval = {
        "id": "approval-1",
        "entity_type": "task",
        "entity_id": "task-1",
        "entity_version": 2,
        "payload_hash": "a" * 64,
        "status": "approved",
        "decision_by": "operator",
        "requested_by": "agent",
    }
    graph = _approval_graph(approval)
    assert "__interrupt__" in graph.invoke({}, config)
    try:
        graph.invoke(
            Command(
                resume={
                    "decision": "approved",
                    "actor": "operator",
                    "approval_id": "approval-1",
                }
            ),
            config,
        )
    except PermissionError as exc:
        assert str(exc) == "APPROVAL_SUBJECT_CHANGED"
    else:
        raise AssertionError("stale approval should be rejected")
