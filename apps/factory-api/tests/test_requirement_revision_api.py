import os
import uuid
from dataclasses import replace

from factory_api import main
from factory_api.database import get_db
from factory_api.routers import agent_conversations
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import (
    AuditRecord,
    ConversationBinding,
    Demand,
    EventOutbox,
    RequirementRevision,
)


class ConversationAdapter:
    def __init__(self):
        self.created = 0
        self.sent = 0
        self.thread_id = f"planner-revision-thread-{uuid.uuid4()}"

    def create_thread(self, *, title, bot_handle):
        self.created += 1
        return self.thread_id

    def send_message(self, _thread_id, *, content, recipient):
        self.sent += 1
        return "planner-revision-message"

    def poll_events(self, _thread_id, *, limit):
        return {"messages": [], "active": False}


def test_requirement_revision_is_hash_bound_and_planner_waits_for_operator(tmp_path, monkeypatch):
    database_url = os.environ.get("DATABASE_URL")
    sqlite_fallback = database_url is None
    engine = create_engine(
        database_url or f"sqlite:///{tmp_path / 'requirement-revision.db'}"
    )
    if sqlite_fallback:
        Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    demand_id = None
    revision_ids = []

    def override_db():
        with factory() as session:
            yield session

    adapter = ConversationAdapter()
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    monkeypatch.setattr(agent_conversations, "_adapter", lambda: adapter)
    main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(main.app) as client:
            demand_response = client.post(
                "/api/v1/demands",
                json={
                    "source": "manual",
                    "external_id": f"tag-revision-api-{uuid.uuid4()}",
                    "title": "Shared client tags",
                    "demand_type": "feature",
                    "requirement": "Organize clients with shared labels and filter by one label.",
                    "acceptance": ["Organize clients with shared labels and filter by one label."],
                },
            )
            assert demand_response.status_code == 201
            demand_id = demand_response.json()["id"]
            demand_version = demand_response.json()["version"]

            blocked = client.post(
                f"/api/v1/demands/{demand_id}/conversation/messages",
                json={"persona": "planner", "content": "Create the task DAG."},
            )
            assert blocked.status_code == 409
            assert blocked.json()["detail"]["code"] == "REQUIREMENT_APPROVAL_REQUIRED"
            assert adapter.created == 0 and adapter.sent == 0

            proposed = client.post(
                f"/api/v1/demands/{demand_id}/revisions",
                json={
                    "expected_demand_version": demand_version,
                    "content": "Clients have a shared tag catalog and can be filtered by one tag.",
                    "acceptance": [
                        "When a client is assigned a tag, the system shall persist "
                        "the association.",
                        "When the operator filters by one tag, the system shall show "
                        "matching clients.",
                    ],
                },
            )
            assert proposed.status_code == 201
            revision = proposed.json()
            revision_id = revision["id"]
            revision_ids.append(revision_id)
            assert revision["decision"] == "proposed"
            assert revision["version"] == 2

            wrong_hash = client.post(
                f"/api/v1/demands/{demand_id}/revisions/2/decision",
                json={
                    "expected_demand_version": demand_version + 1,
                    "revision_sha256": "0" * 64,
                    "decision": "approved",
                    "comment": "Approve the exact reviewed requirement.",
                },
            )
            assert wrong_hash.status_code == 409
            assert wrong_hash.json()["detail"]["code"] == "REQUIREMENT_REVISION_HASH_STALE"

            approved = client.post(
                f"/api/v1/demands/{demand_id}/revisions/2/decision",
                json={
                    "expected_demand_version": demand_version + 1,
                    "revision_sha256": revision["revision_sha256"],
                    "decision": "approved",
                    "comment": "Approve the exact reviewed requirement.",
                },
            )
            assert approved.status_code == 200
            assert approved.json()["decision"] == "approved"
            replayed = client.post(
                f"/api/v1/demands/{demand_id}/revisions/2/decision",
                json={
                    "expected_demand_version": demand_version + 1,
                    "revision_sha256": revision["revision_sha256"],
                    "decision": "approved",
                    "comment": "Replay the exact approval request.",
                },
            )
            assert replayed.status_code == 200
            assert replayed.json()["replayed"] is True

            planner = client.post(
                f"/api/v1/demands/{demand_id}/conversation/messages",
                json={"persona": "planner", "content": "Draft the scoped DAG."},
            )
            assert planner.status_code == 200, planner.text
            assert adapter.created == 1 and adapter.sent == 1

            changes = client.post(
                f"/api/v1/demands/{demand_id}/revisions",
                json={
                    "expected_demand_version": demand_version + 1,
                    "content": "Add explicit behavior for pending and recoverable tag errors.",
                    "acceptance": [
                        (
                            "When a tag request is pending, the UI shall keep the selection "
                            "and show progress."
                        ),
                        (
                            "If a tag request fails, the UI shall show a recoverable error "
                            "without false success."
                        ),
                    ],
                },
            )
            assert changes.status_code == 201
            changes_revision = changes.json()
            revision_ids.append(changes_revision["id"])
            assert changes_revision["version"] == 3
            needs_changes = client.post(
                f"/api/v1/demands/{demand_id}/revisions/3/decision",
                json={
                    "expected_demand_version": demand_version + 2,
                    "revision_sha256": changes_revision["revision_sha256"],
                    "decision": "needs_changes",
                    "comment": "Revise this proposal before it is accepted.",
                },
            )
            assert needs_changes.status_code == 200
            assert needs_changes.json()["decision"] == "needs_changes"

            rejected = client.post(
                f"/api/v1/demands/{demand_id}/revisions",
                json={
                    "expected_demand_version": demand_version + 2,
                    "content": "This separate out-of-scope proposal is rejected.",
                    "acceptance": ["When out of scope, the system shall not ship the request."],
                },
            )
            assert rejected.status_code == 201
            rejected_revision = rejected.json()
            revision_ids.append(rejected_revision["id"])
            assert rejected_revision["version"] == 4
            rejected_decision = client.post(
                f"/api/v1/demands/{demand_id}/revisions/4/decision",
                json={
                    "expected_demand_version": demand_version + 3,
                    "revision_sha256": rejected_revision["revision_sha256"],
                    "decision": "rejected",
                    "comment": "Keep the approved scope and preserve this rejection in history.",
                },
            )
            assert rejected_decision.status_code == 200
            assert rejected_decision.json()["decision"] == "rejected"

        with factory() as session:
            revisions = session.scalars(
                select(RequirementRevision)
                .where(RequirementRevision.demand_id == demand_id)
                .order_by(RequirementRevision.version)
            ).all()
            assert [row.decision for row in revisions] == [
                "proposed", "approved", "needs_changes", "rejected"
            ]
            assert revisions[1].content == (
                "Clients have a shared tag catalog and can be filtered by one tag."
            )
            audit = session.scalars(
                select(AuditRecord).where(
                    AuditRecord.subject_type == "requirement_revision",
                    AuditRecord.subject_id.in_(revision_ids),
                )
            ).all()
            assert [row.action for row in audit].count("requirement_revision.created") == 3
            assert [row.action for row in audit].count("requirement_revision.approved") == 1
            assert [row.action for row in audit].count("requirement_revision.needs_changes") == 1
            assert [row.action for row in audit].count("requirement_revision.rejected") == 1
            events = session.scalars(
                select(EventOutbox).where(
                    EventOutbox.event_type == "requirement.revision.decided",
                    EventOutbox.event_id.in_(
                        [f"requirement-revision-decision:{item}" for item in revision_ids]
                    ),
                )
            ).all()
            assert len(events) == 3
            assert {event.payload["revision_sha256"] for event in events} == {
                revision["revision_sha256"],
                changes_revision["revision_sha256"],
                rejected_revision["revision_sha256"],
            }
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        if demand_id is not None:
            with factory.begin() as session:
                session.execute(
                    delete(ConversationBinding).where(
                        ConversationBinding.thread_id == adapter.thread_id
                    )
                )
                demand = session.get(Demand, demand_id)
                if demand is not None:
                    session.delete(demand)
                session.execute(
                    delete(EventOutbox).where(
                        EventOutbox.event_id.in_(
                            [f"requirement-revision-decision:{item}" for item in revision_ids]
                        )
                    )
                )
                session.execute(delete(AuditRecord).where(AuditRecord.subject_id == demand_id))
                if revision_ids:
                    session.execute(
                        delete(AuditRecord).where(AuditRecord.subject_id.in_(revision_ids))
                    )
        engine.dispose()
