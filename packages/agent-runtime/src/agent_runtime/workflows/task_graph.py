"""Default task workflow with guarded completion and injectable side effects."""

from __future__ import annotations

from typing import Literal, TypedDict


class TaskGraphState(TypedDict, total=False):
    task_id: str
    status: Literal["running", "blocked", "failed", "done"]
    # Keep the operational payload in the graph schema. LangGraph drops keys that
    # are not declared here, which otherwise loses provenance between preflight,
    # worktree creation, model execution, gates, and review.
    base_sha: str
    requirement_revision_id: str
    model_id: str
    model_digest: str
    allowed_paths: list[str]
    worktree: str
    run_id: str
    context: dict[str, object]
    context_sha256: str
    result_sha: str
    tree_hash: str
    gate_status: str
    gate_stdout_sha256: str
    patch_sha256: str
    changed_paths: list[str]
    review_status: str
    review_confidence: float
    review_model: str
    review_digest: str
    prompt_tokens: int
    completion_tokens: int
    preflight_ok: bool
    policy_ok: bool
    context_ready: bool
    execution_ok: bool
    check_exit_code: int
    retry_count: int
    retry_limit: int
    error: str
    compensation_required: bool
    approval_required: bool
    approval_granted: bool


def _verified(state: TaskGraphState) -> TaskGraphState:
    code = state.get("check_exit_code")
    if code != 0:
        return {"status": "failed", "error": f"CHECK_EXIT_{code}"}
    if state.get("approval_required") and not state.get("approval_granted"):
        return {"status": "blocked", "error": "HUMAN_APPROVAL_REQUIRED"}
    return {"status": "done"}


def _route_preflight(state: TaskGraphState) -> str:
    return "policy" if state.get("preflight_ok") else "blocked"


def _route_policy(state: TaskGraphState) -> str:
    return "context" if state.get("policy_ok") else "blocked"


def _route_execution(state: TaskGraphState) -> str:
    if state.get("execution_ok"):
        return "verify"
    if state.get("retry_count", 0) < state.get("retry_limit", 0):
        return "execute"
    return "compensate" if state.get("compensation_required") else "failed"


def _route_verification(state: TaskGraphState) -> str:
    check_exit = state.get("check_exit_code")
    if check_exit != 0:
        return "failed"
    if state.get("approval_required") and not state.get("approval_granted"):
        return "blocked"
    return "done"


def build_task_graph(
    *,
    preflight,
    policy,
    context,
    execute,
    verify,
    compensate,
):
    """Build a LangGraph task DAG; operational actions are supplied by callers."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError("INSTALL_AGENT_RUNTIME_WITH_LANGGRAPH_EXTRAS") from exc

    graph = StateGraph(TaskGraphState)
    nodes = {
        "preflight": preflight,
        "policy": policy,
        "context": context,
        "execute": execute,
        "verify": verify,
        "compensate": compensate,
        "done": _verified,
        "blocked": lambda state: {
            "status": "blocked", "error": state.get("error", "GUARD_REJECTED")
        },
        "failed": lambda state: {
            "status": "failed", "error": state.get("error", "RETRIES_EXHAUSTED")
        },
    }
    for name, node in nodes.items():
        graph.add_node(name, node)
    graph.add_edge(START, "preflight")
    graph.add_conditional_edges(
        "preflight", _route_preflight, {"policy": "policy", "blocked": "blocked"}
    )
    graph.add_conditional_edges(
        "policy", _route_policy, {"context": "context", "blocked": "blocked"}
    )
    graph.add_edge("context", "execute")
    graph.add_conditional_edges("execute", _route_execution, {
        "verify": "verify", "execute": "execute", "compensate": "compensate", "failed": "failed"
    })
    graph.add_conditional_edges("verify", _route_verification, {
        "done": "done", "blocked": "blocked", "failed": "failed"
    })
    graph.add_edge("compensate", "failed")
    for terminal in ("done", "blocked", "failed"):
        graph.add_edge(terminal, END)
    return graph
