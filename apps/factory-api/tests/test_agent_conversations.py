from types import SimpleNamespace
from unittest.mock import MagicMock

from factory_api.routers.agent_conversations import (
    _conversation_view,
    _has_repository_path_citation,
    _persona_response_instructions,
    _repository_evidence,
)


def test_analyst_prompt_allows_read_only_discovery_and_forbids_private_reasoning():
    prompt = _persona_response_instructions("analyst")

    assert "manifesto verificado abaixo" in prompt
    assert "inspeção de código somente leitura" in prompt
    assert "não escreva arquivos" in prompt
    assert "raciocínio privado" in prompt
    assert "FATOS" in prompt and "CONTRATO PROPOSTO" in prompt
    assert "decisão persistida" in prompt
    assert "Clarify demand using traceable evidence" in prompt
    assert "search_allowed_code" in prompt
    assert "`find_files`, `search_code`, `list_files`, and `read_file`" in prompt
    assert "caminho completo e a linha exatos" in prompt
    assert "não produza código, diff" in prompt


def test_planner_refuses_to_plan_until_requirement_is_approved():
    prompt = _persona_response_instructions("planner")

    assert "Só produza DAG se requirement_decision for approved" in prompt
    assert "responda apenas BLOQUEADO" in prompt
    assert "não execute tarefas" in prompt


def test_analyst_output_without_repository_path_evidence_is_withheld():
    session = MagicMock()
    session.scalars.return_value.order_by.return_value.all.return_value = []
    binding = SimpleNamespace(thread_id="analyst-thread", persona="analyst", entity_id="demand-1")
    adapter = SimpleNamespace(
        poll_events=lambda *_args, **_kwargs: {
            "active": False,
            "messages": [
                {
                    "id": "unsupported",
                    "sender_kind": "bot",
                    "sender_name": "Analyst",
                    "content": "FATOS: a busca por etiqueta existe.",
                },
                {
                    "id": "supported",
                    "sender_kind": "bot",
                    "sender_name": "Analyst",
                    "content": (
                        "FATOS: rota observada em "
                        "apps/customer-registry/api/src/main.py:42."
                    ),
                },
            ],
        }
    )

    result = _conversation_view(
        session,
        binding,
        adapter,
        SimpleNamespace(source="manual", repository_id="self"),
    )

    answers = [message["content"] for message in result["messages"]]
    assert answers[0] == (
        "A resposta do Analyst foi retida por não citar evidências verificáveis do repositório."
    )
    assert "apps/customer-registry/api/src/main.py:42" in answers[1]


def test_analyst_markdown_formatted_path_line_citation_is_accepted():
    evidence = "FATOS: o botão está em `apps/customer-registry/web/src/App.tsx:141`."
    assert _has_repository_path_citation(
        evidence, SimpleNamespace(source="manual")
    )
    assert _has_repository_path_citation(
        evidence, SimpleNamespace(source="github")
    )


def test_analyst_markdown_path_without_line_is_not_accepted():
    evidence = "FATOS: o botão está em `apps/customer-registry/web/src/App.tsx`."
    assert not _has_repository_path_citation(
        evidence, SimpleNamespace(source="manual")
    )


def test_analyst_repository_evidence_comes_from_pinned_workspace(monkeypatch):
    monkeypatch.setenv("FACTORY_REPOSITORY_SHA", "a" * 40)
    monkeypatch.setenv("OPENBOT_WORKING_DIRECTORY", "snapshot")

    class Pack:
        sha256 = "b" * 64
        content = {"L2": [{"path": "apps/customer-registry/web/src/App.tsx", "line": 10}]}

    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.open_snapshot",
        lambda *args, **kwargs: SimpleNamespace(files=frozenset()),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.retrieve_context",
        lambda *args, **kwargs: Pack(),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.build_context_pack",
        lambda **kwargs: Pack(),
    )
    evidence = _repository_evidence(
        "analyst",
        SimpleNamespace(source="manual", repository_id="self"),
        "alterar cor do botao para o tema dark",
    )
    assert evidence["pack_sha256"] == "b" * 64
    assert len(evidence["sha256"]) == 64
    assert evidence["content"]["L2"][0]["path"].endswith("App.tsx")


def test_analyst_repository_evidence_is_not_attached_to_github_demand(monkeypatch):
    assert _repository_evidence(
        "analyst",
        SimpleNamespace(
            source="github", repository_id="self", external_id="owner/other#3"
        ),
        "alterar cor do botao para o tema dark",
    ) is None


def test_github_analyst_evidence_requires_the_configured_repository(monkeypatch):
    monkeypatch.setenv("FACTORY_REPOSITORY_SHA", "a" * 40)
    monkeypatch.setenv("OPENBOT_WORKING_DIRECTORY", "snapshot")
    monkeypatch.setenv("GITHUB_OWNER", "owner")
    monkeypatch.setenv("GITHUB_REPO", "repo")

    class Pack:
        sha256 = "b" * 64
        content = {"L2": [{"path": "apps/customer-registry/web/src/App.tsx", "line": 10}]}

    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.open_snapshot",
        lambda *args, **kwargs: SimpleNamespace(files=frozenset()),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.retrieve_context",
        lambda *args, **kwargs: Pack(),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.build_context_pack",
        lambda **kwargs: Pack(),
    )

    demand = SimpleNamespace(
        source="github", repository_id="self", external_id="OWNER/REPO#3"
    )
    assert _repository_evidence("analyst", demand, "dark button") is not None
    demand.external_id = "owner/other#3"
    assert _repository_evidence("analyst", demand, "dark button") is None


def test_evidence_pack_records_exact_token_search_absence(monkeypatch):
    monkeypatch.setenv("FACTORY_REPOSITORY_SHA", "a" * 40)
    monkeypatch.setenv("OPENBOT_WORKING_DIRECTORY", "snapshot")
    source_path = "apps/customer-registry/web/src/styles.css"

    class Pack:
        sha256 = "b" * 64
        content = {"L2": [{"path": source_path, "line": 2, "text": ":root{--green:#3e664e}"}]}

    def retrieve(_snapshot, query, **_kwargs):
        return SimpleNamespace(
            content={"L2": [] if query == "--button-dark" else Pack.content["L2"]}
        )

    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.open_snapshot",
        lambda *args, **kwargs: SimpleNamespace(files=frozenset({source_path})),
    )
    monkeypatch.setattr("factory_api.routers.agent_conversations.retrieve_context", retrieve)
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.build_context_pack",
        lambda **kwargs: Pack(),
    )
    evidence = _repository_evidence(
        "analyst",
        SimpleNamespace(source="manual", repository_id="self"),
        "dark button",
    )
    token_search = next(item for item in evidence["searches"] if item["query"] == "--button-dark")
    assert token_search["searched_paths"] == [source_path]
    assert token_search["matches"] == []


def test_telegram_analyst_can_use_only_the_configured_self_snapshot(monkeypatch):
    monkeypatch.setenv("FACTORY_REPOSITORY_SHA", "a" * 40)
    monkeypatch.setenv("OPENBOT_WORKING_DIRECTORY", "snapshot")

    class Pack:
        sha256 = "b" * 64
        content = {"L2": [{"path": "apps/customer-registry/web/src/App.tsx", "line": 10}]}

    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.open_snapshot",
        lambda *args, **kwargs: SimpleNamespace(files=frozenset()),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.retrieve_context",
        lambda *args, **kwargs: Pack(),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.build_context_pack",
        lambda **kwargs: Pack(),
    )
    assert _repository_evidence(
        "analyst", SimpleNamespace(source="telegram", repository_id="self"), "dark button"
    ) is not None


def test_manual_analyst_requirement_citation_is_allowed_but_not_for_github():
    answer = "Escopo: ver specs/demands/dark-button-e2e/README.md."
    assert _has_repository_path_citation(answer, SimpleNamespace(source="manual"))
    assert not _has_repository_path_citation(answer, SimpleNamespace(source="github"))


def test_minified_css_context_keeps_only_theme_and_target_button_rules(monkeypatch):
    monkeypatch.setenv("FACTORY_REPOSITORY_SHA", "a" * 40)
    monkeypatch.setenv("OPENBOT_WORKING_DIRECTORY", "snapshot")

    css = (
        ":root{color:#202820;background:#f5f7f4;--green:#3e664e}"
        ".other{background:red}.submit-button{background:#3d6248;color:#fff}"
        ".submit-button:hover{background:#2e5039}"
        ".submit-button:focus-visible{outline:2px solid #202820}"
        ".submit-button:disabled{opacity:.6}"
    )
    snippets = [
        {"path": "apps/customer-registry/web/src/styles.css", "line": 2,
         "blob_sha": "c" * 40, "text": css}
    ]
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.open_snapshot",
        lambda *args, **kwargs: SimpleNamespace(files=frozenset()),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.retrieve_context",
        lambda *args, **kwargs: SimpleNamespace(content={"L2": snippets}),
    )
    monkeypatch.setattr(
        "factory_api.routers.agent_conversations.build_context_pack",
        lambda **kwargs: SimpleNamespace(
            sha256="b" * 64, content={"L2": kwargs["snippets"]}
        ),
    )

    evidence = _repository_evidence(
        "analyst", SimpleNamespace(source="manual", repository_id="self"), "button"
    )
    rendered = " ".join(item["text"] for item in evidence["content"]["L2"])
    assert ":root{color:#202820;background:#f5f7f4;--green:#3e664e}" in rendered
    assert ".submit-button{background:#3d6248;color:#fff}" in rendered
    assert ".submit-button:hover{background:#2e5039}" in rendered
    assert ".submit-button:focus-visible{outline:2px solid #202820}" in rendered
    assert ".submit-button:disabled{opacity:.6}" in rendered
    assert all(len(item["text"]) < 500 for item in evidence["content"]["L2"])
    assert ".other" not in rendered
