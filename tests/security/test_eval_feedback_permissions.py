from dataclasses import replace
from uuid import uuid4

from factory_api import main
from factory_api.auth.session import create_session
from factory_api.database import get_db
from factory_api.routers import eval_feedback
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import AgentRun, AuditRecord, Demand, RequirementRevision, RunFeedback, Task


def test_feedback_requires_authenticated_operator_and_is_immutable(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'feedback.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    demand_id = str(uuid4())
    task_id = str(uuid4())
    run_id = str(uuid4())
    with factory() as session:
        demand = Demand(
            id=demand_id,
            source="manual",
            external_id="feedback-test",
            title="Feedback test",
            demand_type="feature",
            status="new",
            version=2,
            state_version=1,
            risk="normal",
            repository_id="self",
        )
        session.add(demand)
        session.flush()
        session.add(
            Task(
                id=task_id,
                demand_id=demand_id,
                title="Feedback task",
                owner_role="qa",
                status="done",
                priority=50,
                path_scopes=["tests/**"],
                acceptance=["pass"],
                risk="normal",
                expected_demand_version=2,
                state_version=1,
                fencing_token=0,
            )
        )
        revision = RequirementRevision(
            demand_id=demand_id,
            version=2,
            content="approved requirement",
            acceptance=[],
            decision="approved",
        )
        session.add(revision)
        session.flush()
        session.add(
            AgentRun(
                id=run_id,
                task_id=task_id,
                attempt=1,
                model_id="executor-v1",
                model_digest="sha256:abc",
                prompt_hash="a" * 64,
                context_hash="b" * 64,
                skill_hash="c" * 64,
                requirement_revision_id=revision.id,
                base_git_sha="d" * 40,
                status="completed",
            )
        )
        session.commit()

    settings = replace(
        main.settings, auth_enabled=True, secret_key="x" * 48, password_hash="test-hash"
    )
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(eval_feedback.Settings, "from_env", classmethod(lambda _cls: settings))
    main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(main.app) as client:
            payload = {
                "run_id": run_id,
                "task_id": task_id,
                "decision": "reject",
                "error_category": "tests",
                "comment": "Missing regression case.",
                "prompt_hash": "a" * 64,
                "model_id": "executor-v1",
                "requirement_version": 2,
                "evidence_refs": ["artifact:pytest"],
            }
            assert client.post("/api/v1/evals/feedback", json=payload).status_code == 401
            token, csrf = create_session(settings.secret_key)
            client.cookies.set("factory_session", token)
            headers = {"X-CSRF-Token": csrf}
            response = client.post("/api/v1/evals/feedback", json=payload, headers=headers)
            assert response.status_code == 201
            assert response.json()["reviewer_sub"] == "operator"
            assert (
                client.post("/api/v1/evals/feedback", json=payload, headers=headers).status_code
                == 409
            )
            assert client.get("/api/v1/evals/feedback/summary").json()["rework_count"] == 1
        with factory() as session:
            assert len(session.scalars(select(RunFeedback)).all()) == 1
            assert (
                session.scalars(
                    select(AuditRecord).where(AuditRecord.action == "eval.feedback.recorded")
                )
                .one()
                .actor
                == "operator"
            )
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()
