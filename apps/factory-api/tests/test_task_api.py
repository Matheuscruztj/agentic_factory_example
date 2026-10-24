from __future__ import annotations

from dataclasses import replace

import pytest
from factory_api import main
from factory_api.database import get_db
from factory_api.routers import events
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from task_engine.models import AuditRecord, Demand, TransitionEvent


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    main.app.dependency_overrides[get_db] = override_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    engine.dispose()


def test_demands_tasks_and_versioned_transitions(client: TestClient) -> None:
    response = client.post(
        "/api/v1/demands",
        json={
            "source": "manual",
            "external_id": "fac-28",
            "title": "Add API",
            "demand_type": "feature",
            "requirement": "Expose typed task API",
            "acceptance": ["Duplicate intake returns conflict"],
        },
    )
    assert response.status_code == 201
    demand_id = response.json()["id"]
    assert (
        client.post(
            "/api/v1/demands",
            json={
                "source": "manual",
                "external_id": "fac-28",
                "title": "Duplicate",
                "demand_type": "feature",
                "requirement": "same",
                "acceptance": ["x"],
            },
        ).status_code
        == 409
    )
    first = client.post(
        f"/api/v1/demands/{demand_id}/tasks", json={"title": "Analysis", "owner_role": "analyst"}
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/demands/{demand_id}/tasks",
        json={"title": "Implement", "owner_role": "backend", "dependencies": [first.json()["id"]]},
    )
    assert second.status_code == 201
    assert second.json()["dependencies"] == [first.json()["id"]]
    transition = client.post(
        f"/api/v1/tasks/{first.json()['id']}/transition",
        json={
            "new_state": "ready",
            "expected_version": 1,
            "reason": "Task planned",
            "idempotency_key": "ready-1",
        },
    )
    assert transition.status_code == 200 and transition.json()["status"] == "ready"
    stale = client.post(
        f"/api/v1/tasks/{first.json()['id']}/transition",
        json={
            "new_state": "leased",
            "expected_version": 1,
            "reason": "stale",
            "idempotency_key": "stale-1",
        },
    )
    assert stale.status_code == 409
    detail = client.get(f"/api/v1/demands/{demand_id}").json()
    assert len(detail["revisions"]) == 1 and len(detail["tasks"]) == 2
    second_ready = client.post(
        f"/api/v1/tasks/{second.json()['id']}/transition",
        json={
            "new_state": "ready",
            "expected_version": 1,
            "reason": "Task planned",
            "idempotency_key": "ready-2",
        },
    )
    assert second_ready.status_code == 200
    simulation = client.post(f"/api/v1/demands/{demand_id}/run-fake")
    assert simulation.status_code == 200
    assert simulation.json()["completed_task_ids"] == [first.json()["id"], second.json()["id"]]
    assert (
        simulation.json()["model_called"] is False
        and simulation.json()["approval_required"] is True
    )


def test_human_approval_is_immutable_and_version_bound(client: TestClient) -> None:
    demand = client.post(
        "/api/v1/demands",
        json={
            "source": "manual",
            "external_id": "approval-1",
            "title": "Approval",
            "demand_type": "feature",
            "requirement": "Review me",
            "acceptance": ["human review"],
        },
    ).json()
    requested = client.post(
        "/api/v1/approvals", json={"entity_type": "demand", "entity_id": demand["id"]}
    )
    assert requested.status_code == 201
    approval_id = requested.json()["id"]
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "approved", "comment": "Reviewed"},
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert (
        client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "rejected", "comment": "Replay"},
        ).status_code
        == 409
    )
    assert client.get("/api/v1/approvals").json() == []
    self_requested = client.post(
        "/api/v1/approvals",
        json={"entity_type": "demand", "entity_id": demand["id"], "requested_by": "operator"},
    ).json()
    self_decision = client.post(
        f"/api/v1/approvals/{self_requested['id']}/decision",
        json={"decision": "approved", "comment": "Must be rejected"},
    )
    assert self_decision.status_code == 403


def test_event_stream_cursor_replays_both_sources_without_sensitive_details(
    tmp_path, monkeypatch
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(events, "SessionFactory", factory)
    with factory.begin() as session:
        demand = Demand(source="manual", external_id="stream", title="Stream", demand_type="bug")
        session.add(demand)
        session.flush()
        session.add(
            AuditRecord(
                subject_type="demand",
                subject_id=demand.id,
                action="created",
                actor="operator",
                details={"token": "secret"},
                evidence_hashes=[],
            )
        )
        session.add(
            TransitionEvent(
                entity_type="demand",
                entity_id=demand.id,
                from_state="new",
                to_state="triage",
                expected_version=1,
                actor="operator",
                reason="private reason",
                idempotency_key="transition-1",
            )
        )
    cursors = events._decode_cursor(None)
    first = events._load_events(cursors)
    assert len(first) == 2
    for created_at, row_id, source, payload in first:
        cursors[source] = (created_at, row_id)
        assert "secret" not in str(payload) and "private reason" not in str(payload)
    encoded = events._encode_cursor(cursors)
    assert events._decode_cursor(encoded) == cursors
    with factory.begin() as session:
        session.add(
            AuditRecord(
                subject_type="demand",
                subject_id="d1",
                action="updated",
                actor="operator",
                details={},
                evidence_hashes=[],
            )
        )
    replayed = events._load_events(events._decode_cursor(encoded))
    assert len(replayed) == 1 and replayed[0][3]["action"] == "updated"
    engine.dispose()
