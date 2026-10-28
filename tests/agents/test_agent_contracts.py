import pytest
from agent_runtime.collaboration import CollaborationBudget, CollaborationLimitError
from agent_runtime.intent_router import IntentKind, route_conversation_intent
from agent_runtime.openbot_adapter import OpenBotAdapter, OpenBotError
from agent_runtime.tool_gateway import ToolDenied, ToolGateway
from context_engine.binding import BindingError, bind_thread
from shared_contracts.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from task_engine.models import Demand, Task


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, path, *, body=None, query=None):
        self.calls.append((method, path, body, query))
        if path == "/api/v1/threads":
            return {"thread": {"id": "thread-1"}}
        if path.endswith("/messages"):
            return {"message": {"id": "message-1"}}
        if "/cancel" in path:
            return {"cancelled": True}
        return {"thread": {"id": "thread-1"}, "messages": []}


def test_openbot_adapter_uses_internal_contract_and_intent_is_inert() -> None:
    transport = FakeTransport()
    adapter = OpenBotAdapter(transport)
    thread = adapter.create_thread(title="Issue", bot_handle="@qa")
    assert thread == "thread-1"
    assert transport.calls[0][2]["handles"] == ["you", "qa"]
    assert transport.calls[0][2]["default_bot_handle"] == "qa"
    scoped_thread = adapter.create_thread(
        title="Baseline discovery", bot_handle="analyst", working_directory="baseline/sha"
    )
    assert scoped_thread == "thread-1"
    assert transport.calls[1][2]["working_directory"] == "baseline/sha"
    assert adapter.send_message(thread, content="Review", recipient="@qa") == "message-1"
    assert transport.calls[2][2]["to"] == ["qa"]
    assert adapter.poll_events(thread)["messages"] == []
    with pytest.raises(OpenBotError, match="INVALID_UPSTREAM_ID"):
        adapter.find_thread("../.env")
    for path in ("../outside", "/etc", "a/../../b", r"a\b"):
        with pytest.raises(OpenBotError, match="INVALID_WORKING_DIRECTORY"):
            adapter.create_thread(title="Unsafe", bot_handle="analyst", working_directory=path)

    assert route_conversation_intent("How can I fix this test?").kind is IntentKind.ASK
    proposal = route_conversation_intent("Fix this regression")
    assert proposal.kind is IntentKind.WRITE
    assert proposal.proposal and not proposal.proposal.executable
    assert proposal.invoke_workflow is False


def test_portuguese_dark_button_change_becomes_inert_proposal() -> None:
    for request in (
        "alterar cor do botao para o tema dark",
        "quero alterar a cor do botão para o tema dark",
    ):
        intent = route_conversation_intent(request)
        assert intent.kind is IntentKind.WRITE
        assert intent.proposal is not None
        assert intent.proposal.executable is False
        assert intent.proposal.requires_human_review is True


def test_negated_proposal_instruction_stays_read_only() -> None:
    intent = route_conversation_intent(
        "Não proponha uma alteração agora; liste somente as ambiguidades do requisito."
    )
    assert intent.kind is IntentKind.READ
    assert intent.proposal is None
    assert intent.invoke_workflow is False


def test_dark_button_discovery_does_not_create_an_executable_proposal() -> None:
    intent = route_conversation_intent(
        "alterar cor do botao para o tema dark. Faça discovery somente leitura, "
        "identifique o botão e liste as ambiguidades. Não implemente."
    )

    assert intent.kind is IntentKind.READ
    assert intent.proposal is None
    assert intent.invoke_workflow is False


def test_thread_bindings_are_immutable_and_gateway_denies_secrets(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'bindings.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        demand = Demand(
            source="github", external_id="42", title="bug", demand_type="bug"
        )
        session.add(demand)
        session.flush()
        task = Task(demand_id=demand.id, title="qa", owner_role="qa", status="ready")
        session.add(task)
        session.flush()
        bind_thread(
            session,
            thread_id="thread-1",
            reference="ISSUE-42",
            persona="qa",
            participants=["operator", "@qa"],
            snapshot_sha="a" * 40,
            policy_id="qa-v1",
        )
        with pytest.raises(BindingError, match="THREAD_ALREADY_BOUND"):
            bind_thread(
                session,
                thread_id="thread-1",
                reference=f"TASK-{task.id}",
                persona="qa",
                participants=["operator", "@qa"],
                snapshot_sha="b" * 40,
                policy_id="qa-v1",
            )
        session.commit()

    calls = []
    gateway = ToolGateway(
        load_binding=lambda _key: {
            "persona": "qa", "entity_id": "demand-id", "entity_type": "demand"
        },
        path_policy=lambda _binding: {"src/app.py", ".env", "../secrets.txt"},
        issue_context=lambda _entity: {"title": "authorized", "token": "secret-value"},
        task_status=lambda _entity: {},
        search_code=lambda query, scope: calls.append((query, scope)) or [
            {"path": path, "sha": "a" * 40, "text": "contents"}
            for path in ["src/app.py", ".env"]
        ],
        store_proposal=lambda binding, proposal: {"title": proposal.title},
    )
    result = gateway.invoke(
        actor="operator", binding_id="thread-1", tool="search_allowed_code",
        arguments={"query": "secret"},
    )
    assert calls == [("secret", {"src/app.py"})]
    assert [row["path"] for row in result["results"]] == ["src/app.py"]
    denied = ToolGateway(
        load_binding=lambda _key: None,
        path_policy=lambda _binding: set(),
        issue_context=lambda _entity: {}, task_status=lambda _entity: {},
        search_code=lambda _query, _scope: [],
        store_proposal=lambda _binding, _proposal: {},
    )
    with pytest.raises(ToolDenied, match="THREAD_BINDING_REQUIRED"):
        denied.invoke(actor="operator", binding_id="none", tool="get_issue_context", arguments={})


def test_collaboration_budget_bounds_loops_and_calls() -> None:
    budget = CollaborationBudget(max_hops=1, max_calls=1, max_repeats=0)
    budget.observe_message(sender="@qa", content="review")
    with pytest.raises(CollaborationLimitError, match="MAX_AGENT_HOPS"):
        budget.observe_message(sender="@backend", content="another")
    budget.consume_call()
    with pytest.raises(CollaborationLimitError, match="MAX_AGENT_CALLS"):
        budget.consume_call()
