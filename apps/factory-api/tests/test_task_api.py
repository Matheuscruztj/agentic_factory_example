from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from factory_api import main
from factory_api.database import get_db
from factory_api.routers import events
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from task_engine.models import (
    AgentRun,
    Artifact,
    AuditRecord,
    Demand,
    EventOutbox,
    GateEvidence,
    TransitionEvent,
)


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
        test_client.app.state.test_session_factory = factory
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
    revision = detail["revisions"][0]
    assert revision["ears_clauses"][0]["requires_clarification"] is True
    assert [item["polarity"] for item in revision["scenarios"]] == ["positive", "negative"]
    assert revision["clarifications"]
    assert detail["tasks"][0]["runs"] == []
    second_ready = client.post(
        f"/api/v1/tasks/{second.json()['id']}/transition",
        json={
            "new_state": "ready",
            "expected_version": 1,
            "reason": "Task planned",
            "idempotency_key": "ready-2",
        },
    )
    assert second_ready.status_code == 409
    simulation = client.post(f"/api/v1/demands/{demand_id}/run-fake")
    assert simulation.status_code == 200
    assert simulation.json()["reviewed_task_ids"] == [first.json()["id"]]
    assert (
        simulation.json()["model_called"] is False
        and simulation.json()["human_review_required"] is True
    )


def test_demand_detail_returns_sha_bound_runs_gates_and_artifacts(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    demand = client.post(
        "/api/v1/demands",
        json={
            "source": "manual",
            "external_id": "run-detail",
            "title": "Run detail",
            "demand_type": "feature",
            "requirement": "show proof",
            "acceptance": ["SHA-bound"],
        },
    ).json()
    task = client.post(
        f"/api/v1/demands/{demand['id']}/tasks",
        json={"title": "Implement", "owner_role": "backend"},
    ).json()
    detail = client.get(f"/api/v1/demands/{demand['id']}").json()
    revision_id = detail["revisions"][0]["id"]
    session_factory = client.app.state.test_session_factory
    diff = b"diff --git a/src/value.py b/src/value.py\n+value = 2\n"
    with session_factory() as session:
        run = AgentRun(
            task_id=task["id"],
            attempt=1,
            model_id="local-test",
            model_digest="sha256:test",
            prompt_hash="a" * 64,
            context_hash="b" * 64,
            skill_hash="c" * 64,
            requirement_revision_id=revision_id,
            base_git_sha="1" * 40,
            result_git_sha="2" * 40,
            tree_hash="3" * 40,
            status="passed",
        )
        session.add(run)
        session.flush()
        session.add(
            GateEvidence(
                run_id=run.id,
                task_id=task["id"],
                attempt=1,
                check_name="unit",
                status="pass",
                git_sha="2" * 40,
                tree_hash="3" * 40,
                suite_hash="4" * 64,
                tool_hash="5" * 64,
                config_hash="6" * 64,
                artifact_sha256="7" * 64,
            )
        )
        session.add(
            Artifact(
                subject_type="run",
                subject_id=run.id,
                relative_path=f"artifacts/run/{run.id}/changes.diff",
                sha256=hashlib.sha256(diff).hexdigest(),
                size_bytes=len(diff),
                media_type="text/x-diff",
            )
        )
        session.commit()
    artifact_path = tmp_path / "artifacts" / "run" / run.id / "changes.diff"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(diff)

    task_view = client.get(f"/api/v1/demands/{demand['id']}").json()["tasks"][0]
    assert task_view["runs"][0]["result_git_sha"] == "2" * 40
    assert task_view["runs"][0]["gates"][0]["check_name"] == "unit"
    artifact = task_view["runs"][0]["artifacts"][0]
    assert artifact["path"].endswith("changes.diff")
    downloaded = client.get(
        f"/api/v1/demands/{demand['id']}/runs/{run.id}/artifacts/{artifact['id']}"
    )
    assert downloaded.status_code == 200 and downloaded.content == diff
    assert downloaded.headers["x-artifact-sha256"] == hashlib.sha256(diff).hexdigest()
    assert (
        downloaded.headers["content-security-policy"]
        == "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    wrong_demand = client.get(
        f"/api/v1/demands/{'0' * 36}/runs/{run.id}/artifacts/{artifact['id']}"
    )
    assert wrong_demand.status_code == 404
    artifact_path.write_bytes(diff + b"tampered")
    assert (
        client.get(
            f"/api/v1/demands/{demand['id']}/runs/{run.id}/artifacts/{artifact['id']}"
        ).status_code
        == 409
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
    pending = client.get("/api/v1/approvals").json()[0]
    assert pending["subject_current"] is True
    assert pending["subject"]["title"] == "Approval"
    assert pending["subject"]["requirement_revisions"][0]["content"] == "Review me"
    assert len(pending["subject"]["requirement_revision_hashes"]) == 1
    assert len(pending["subject"]["plan_hash"]) == 64
    approved = client.post(
        f"/api/v1/approvals/{approval_id}/decision",
        json={"decision": "approved", "comment": "Reviewed"},
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    with client.app.state.test_session_factory() as session:
        event = (
            session.query(EventOutbox).filter_by(event_id=f"approval-decided:{approval_id}").one()
        )
        assert event.event_type == "human.approval.decided"
        assert event.payload["payload_hash"] == requested.json()["payload_hash"]
        assert len(event.payload["requirement_revision_hashes"]) == 1
        assert len(event.payload["plan_hash"]) == 64
        assert event.payload["actor"] == "operator"
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


def test_planning_requests_are_idempotent_and_require_reviewed_requirement(client):
    demand = client.post(
        "/api/v1/demands",
        json={
            "source": "manual",
            "external_id": "planning-api",
            "title": "Plan request",
            "demand_type": "feature",
            "requirement": "Adjust registry button",
            "acceptance": ["Use the agreed dark token"],
        },
    ).json()
    payload = {
        "base_git_sha": "a" * 40,
        "context_paths": ["apps/customer-registry/web/src/App.tsx"],
        "profile": "registry-frontend",
        "idempotency_key": "discovery-once",
    }
    path = f"/api/v1/demands/{demand['id']}/discovery"
    first = client.post(path, json=payload)
    replay = client.post(path, json=payload)
    assert first.status_code == replay.status_code == 202
    assert first.json()["event_id"] == replay.json()["event_id"]
    changed = client.post(path, json={**payload, "context_paths": ["other.py"]})
    assert changed.status_code == 409
    assert client.post(f"/api/v1/demands/{demand['id']}/plan", json=payload).status_code == 409
    unsafe = client.post(
        path, json={**payload, "idempotency_key": "unsafe", "context_paths": ["../.env"]}
    )
    assert unsafe.status_code in {409, 422}


def test_proposed_plan_can_be_revised_but_stale_or_running_plan_cannot(client):
    demand = client.post(
        "/api/v1/demands",
        json={
            "source": "manual",
            "external_id": "plan-revision",
            "title": "Plan revision",
            "demand_type": "feature",
            "requirement": "Implement approved behavior",
            "acceptance": ["Correct behavior"],
        },
    ).json()
    task = client.post(
        f"/api/v1/demands/{demand['id']}/tasks",
        json={
            "title": "Plan revision",
            "owner_role": "backend",
            "path_scopes": ["app.py"],
            "acceptance": ["Correct behavior"],
        },
    ).json()
    body = {
        "expected_version": task["state_version"],
        "title": "Plan revision",
        "owner_role": "backend",
        "path_scopes": ["app.py"],
        "acceptance": ["Correct behavior"],
        "execution_spec": {
            "base_git_sha": "a" * 40,
            "profile": "python-fixture",
            "context_paths": ["app.py"],
            "fixture_path": "tests",
        },
    }
    endpoint = f"/api/v1/tasks/{task['id']}/plan"
    assert client.put(endpoint, json=body).status_code == 200
    assert client.put(endpoint, json=body).status_code == 409
    from task_engine.models import Task

    with client.app.state.test_session_factory.begin() as session:
        row = session.get(Task, task["id"])
        row.status = "running"
    assert (
        client.put(
            endpoint, json={**body, "expected_version": task["state_version"] + 1}
        ).status_code
        == 409
    )


def test_demand_transition_is_idempotent_and_cannot_skip_lifecycle(client):
    demand = client.post(
        "/api/v1/demands",
        json={
            "source": "manual",
            "external_id": "demand-lifecycle",
            "title": "Lifecycle",
            "demand_type": "feature",
            "requirement": "Implement behavior",
            "acceptance": ["Correct behavior"],
        },
    ).json()
    path = f"/api/v1/demands/{demand['id']}/transition"
    body = {
        "new_state": "triage",
        "expected_version": 1,
        "reason": "Review requested work",
        "idempotency_key": "triage",
    }
    first = client.post(path, json=body)
    assert first.status_code == 200
    assert client.post(path, json=body).json()["transition_id"] == first.json()["transition_id"]
    response = client.post(
        path,
        json={**body, "new_state": "completed", "expected_version": 2, "idempotency_key": "skip"},
    )
    assert response.status_code == 409
