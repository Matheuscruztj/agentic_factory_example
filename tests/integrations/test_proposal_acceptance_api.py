from dataclasses import replace

from factory_api import main
from factory_api.database import get_db
from factory_api.routers import agent_conversations
from factory_workers.followups import dispatch_approved_follow_up
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import (
    ConversationBinding,
    ConversationTaskProposal,
    Demand,
    EventOutbox,
    RequirementRevision,
    Task,
)


class FakeConversationAdapter:
    def create_thread(self, *, title, bot_handle):
        return "thread-live-smoke"

    def poll_events(self, _thread_id, *, limit):
        return {"messages": [], "active": True}

    def send_message(self, _thread_id, *, content, recipient):
        return "message-live-smoke"


class UnsafeOutputConversationAdapter(FakeConversationAdapter):
    def poll_events(self, _thread_id, *, limit):
        return {
            "messages": [
                {
                    "id": "reasoning-preface",
                    "sender_kind": "bot",
                    "sender_name": "qa",
                    "content": "Okay, let's see. The user wants me to respond with a sentence.",
                },
                {
                    "id": "oversized-answer",
                    "sender_kind": "bot",
                    "sender_name": "qa",
                    "content": "safe-looking " * 1_000,
                },
                {
                    "id": "valid-answer",
                    "sender_kind": "bot",
                    "sender_name": "qa",
                    "content": "A revisão encontrou duas falhas reproduzíveis.",
                },
            ],
            "active": False,
        }


class IsolatedConversationAdapter:
    def __init__(self):
        self.threads = []
        self.prompts = {}

    def create_thread(self, *, title, bot_handle):
        thread_id = f"isolated-{len(self.threads) + 1}"
        self.threads.append((thread_id, title, bot_handle))
        return thread_id

    def poll_events(self, _thread_id, *, limit):
        return {"messages": [], "active": False}

    def send_message(self, thread_id, *, content, recipient):
        self.prompts[thread_id] = (content, recipient)
        return f"message-{thread_id}"


def test_proposal_acceptance_is_hash_bound_scoped_audited_and_idempotent(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'proposal.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    monkeypatch.setattr(agent_conversations, "_adapter", lambda: FakeConversationAdapter())
    main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(main.app) as client:
            demand = client.post(
                "/api/v1/demands",
                json={
                    "source": "manual",
                    "external_id": "proposal-smoke",
                    "title": "Smoke proposal",
                    "demand_type": "feature",
                    "requirement": "Implement an approved follow-up",
                    "acceptance": ["Only reviewed scope is made into a task"],
                },
            ).json()
            opened = client.post(
                f"/api/v1/demands/{demand['id']}/conversation", json={"persona": "qa"}
            )
            assert opened.status_code == 200
            response = client.post(
                f"/api/v1/demands/{demand['id']}/conversation/messages",
                json={"content": "Fix the missing smoke test", "persona": "qa"},
            )
            assert response.status_code == 200
            proposal_id = response.json()["task_proposal"]["id"]
            payload = {
                "payload_hash": response.json()["task_proposal"]["payload_hash"],
                "owner_role": "qa",
                "path_scopes": ["apps/factory-api/tests/**"],
                "acceptance": ["The new regression is covered"],
                "dependencies": [],
                "risk": "normal",
            }
            base = f"/api/v1/demands/{demand['id']}/conversation/proposals/{proposal_id}/accept"
            accepted = client.post(base, json=payload)
            replay = client.post(base, json=payload)
            assert accepted.status_code == 201 and replay.status_code == 201
            assert accepted.json()["task_id"] == replay.json()["task_id"]
            assert client.post(base, json={**payload, "payload_hash": "0" * 64}).status_code == 409
        with factory() as session:
            original_demand = session.get(Demand, demand["id"])
            original_version = original_demand.version
            original_revisions = session.scalars(
                select(RequirementRevision).where(RequirementRevision.demand_id == demand["id"])
            ).all()
            tasks = session.scalars(select(Task).where(Task.demand_id == demand["id"])).all()
            proposals = session.scalars(select(ConversationTaskProposal)).all()
            events = session.scalars(select(EventOutbox)).all()
            assert len(tasks) == 1 and tasks[0].path_scopes == ["apps/factory-api/tests/**"]
            assert len(proposals) == 1 and proposals[0].status == "accepted"
            assert len(events) == 1 and events[0].event_type == "task.follow_up.approved"
            event_id = events[0].event_id
        delivered = []
        result = dispatch_approved_follow_up(
            factory,
            event_id=event_id,
            invoke_subworkflow=lambda key, task_id, context: (
                delivered.append((key, task_id, context)) or "run-follow-up-1"
            ),
        )
        replayed_delivery = dispatch_approved_follow_up(
            factory,
            event_id=event_id,
            invoke_subworkflow=lambda *_args: (_ for _ in ()).throw(
                AssertionError("workflow redelivered after durable inbox receipt")
            ),
        )
        assert result["status"] == "dispatched"
        assert replayed_delivery["status"] == "already_dispatched"
        assert len(delivered) == 1 and delivered[0][2]["discovery"] == "reuse"
        with factory() as session:
            assert session.get(Demand, demand["id"]).version == original_version
            revisions_after = session.scalars(
                select(RequirementRevision).where(RequirementRevision.demand_id == demand["id"])
            ).all()
            assert [row.id for row in revisions_after] == [row.id for row in original_revisions]
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def test_same_persona_threads_keep_two_demand_snapshots_isolated(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'isolated-conversations.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    adapter = IsolatedConversationAdapter()
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    monkeypatch.setattr(agent_conversations, "_adapter", lambda: adapter)
    main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(main.app) as client:
            demands = []
            for external_id, title, requirement in (
                ("card-one", "Alpha card", "ALPHA_REQUIREMENT_ONLY"),
                ("card-two", "Beta card", "BETA_REQUIREMENT_ONLY"),
            ):
                demand = client.post(
                    "/api/v1/demands",
                    json={
                        "source": "manual",
                        "external_id": external_id,
                        "title": title,
                        "demand_type": "feature",
                        "requirement": requirement,
                        "acceptance": [requirement],
                    },
                ).json()
                demands.append(demand)
                opened = client.post(
                    f"/api/v1/demands/{demand['id']}/conversation", json={"persona": "qa"}
                )
                assert opened.status_code == 200
                sent = client.post(
                    f"/api/v1/demands/{demand['id']}/conversation/messages",
                    json={"content": "Summarize this card", "persona": "qa"},
                )
                assert sent.status_code == 200
        assert len(adapter.threads) == 2
        first, second = [entry[0] for entry in adapter.threads]
        assert first != second
        assert "ALPHA_REQUIREMENT_ONLY" in adapter.prompts[first][0]
        assert "BETA_REQUIREMENT_ONLY" not in adapter.prompts[first][0]
        assert "BETA_REQUIREMENT_ONLY" in adapter.prompts[second][0]
        assert "ALPHA_REQUIREMENT_ONLY" not in adapter.prompts[second][0]
        with factory() as session:
            bindings = session.query(ConversationBinding).all()
            assert len(bindings) == 2
            assert {binding.persona for binding in bindings} == {"qa"}
            assert len({binding.entity_id for binding in bindings}) == 2
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def test_conversation_hides_reasoning_like_and_oversized_bot_outputs(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'conversation-output-guard.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    monkeypatch.setattr(
        agent_conversations, "_adapter", lambda: UnsafeOutputConversationAdapter()
    )
    main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(main.app) as client:
            demand = client.post(
                "/api/v1/demands",
                json={
                    "source": "manual",
                    "external_id": "conversation-output-guard",
                    "title": "Safe answer visibility",
                    "demand_type": "question",
                    "requirement": "Read QA response safely",
                    "acceptance": ["Private analysis is not displayed"],
                },
            ).json()
            response = client.post(
                f"/api/v1/demands/{demand['id']}/conversation",
                json={"persona": "qa"},
            )
            assert response.status_code == 200
            messages = response.json()["messages"]
            assert messages[0]["content"] == agent_conversations._WITHHELD_RESPONSE
            assert messages[1]["content"] == agent_conversations._WITHHELD_RESPONSE
            assert messages[2]["content"] == "A revisão encontrou duas falhas reproduzíveis."
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()


def test_negated_proposal_message_does_not_persist_a_task_proposal(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'negated-proposal.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    monkeypatch.setattr(agent_conversations, "_adapter", lambda: FakeConversationAdapter())
    main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(main.app) as client:
            demand = client.post(
                "/api/v1/demands",
                json={
                    "source": "manual",
                    "external_id": "negated-proposal-smoke",
                    "title": "Read-only discovery request",
                    "demand_type": "feature",
                    "requirement": "List open questions without changing scope",
                    "acceptance": ["No task is created"],
                },
            ).json()
            response = client.post(
                f"/api/v1/demands/{demand['id']}/conversation/messages",
                json={
                    "content": "Não proponha uma alteração agora; liste somente as ambiguidades.",
                    "persona": "qa",
                },
            )
            assert response.status_code == 200
            assert response.json()["task_proposal"] is None
        with factory() as session:
            assert session.query(ConversationTaskProposal).count() == 0
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()
