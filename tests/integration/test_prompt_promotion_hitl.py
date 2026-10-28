import hashlib
import json
from dataclasses import replace

from factory_api import main
from factory_api.auth.session import create_session
from factory_api.database import get_db
from factory_api.routers import prompt_releases
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import AuditRecord, PromptRelease


def test_prompt_promotion_requires_explicit_operator_and_rollback_is_audited(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'prompts.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    settings = replace(
        main.settings, auth_enabled=True, secret_key="p" * 48, password_hash="test-hash"
    )
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(prompt_releases.Settings, "from_env", classmethod(lambda _cls: settings))
    experiment_path = tmp_path / "prompt-experiment.json"
    monkeypatch.setattr(prompt_releases, "_EXPERIMENT_REPORT", experiment_path)
    main.app.dependency_overrides[get_db] = override_db
    try:
        def write_experiment(version: str, *, eligible: bool = True, regressions=None) -> str:
            content = (prompt_releases._PROMPT_DIR / f"{version}.md").read_text()
            report = {
                "promotion_eligible": eligible,
                "candidate": {"prompt_hash": hashlib.sha256(content.encode()).hexdigest()},
                "comparison": {"critical_regressions": regressions or []},
            }
            encoded = json.dumps(report, sort_keys=True).encode()
            experiment_path.write_bytes(encoded)
            return hashlib.sha256(encoded).hexdigest()

        with TestClient(main.app) as client:
            baseline_hash = hashlib.sha256(
                (prompt_releases._PROMPT_DIR / "feature-baseline-v1.md").read_bytes()
            ).hexdigest()
            baseline_experiment = write_experiment("feature-baseline-v1")
            baseline_payload = {
                "version": "feature-baseline-v1",
                "prompt_hash": baseline_hash,
                "experiment_sha256": baseline_experiment,
            }
            candidate_content = (
                prompt_releases._PROMPT_DIR / "feature-candidate-v1.md"
            ).read_bytes()
            candidate_hash = hashlib.sha256(candidate_content).hexdigest()
            candidate_payload = {
                "version": "feature-candidate-v1",
                "prompt_hash": candidate_hash,
                "experiment_sha256": "0" * 64,
            }
            assert (
                client.post("/api/v1/prompts/releases/promote", json=baseline_payload).status_code
                == 401
            )
            token, csrf = create_session(settings.secret_key)
            client.cookies.set("factory_session", token)
            headers = {"X-CSRF-Token": csrf}
            assert (
                client.post(
                    "/api/v1/prompts/releases/promote",
                    json=baseline_payload,
                    headers=headers,
                ).status_code
                == 201
            )
            failing_candidate_experiment = write_experiment(
                "feature-candidate-v1", eligible=False, regressions=["critical-case"]
            )
            blocked = client.post(
                "/api/v1/prompts/releases/promote",
                json={**candidate_payload, "experiment_sha256": failing_candidate_experiment},
                headers=headers,
            )
            assert blocked.status_code == 409
            assert blocked.json()["detail"]["code"] == "PROMPT_REGRESSION_NOT_PASSED"
            assert (
                client.get("/api/v1/prompts/releases").json()["active"]["version"]
                == "feature-baseline-v1"
            )
            candidate_experiment = write_experiment("feature-candidate-v1")
            candidate_payload["experiment_sha256"] = candidate_experiment
            assert client.post(
                "/api/v1/prompts/releases/promote",
                json={**candidate_payload, "prompt_hash": "0" * 64},
                headers=headers,
            ).status_code == 409
            promoted = client.post(
                "/api/v1/prompts/releases/promote", json=candidate_payload, headers=headers
            )
            assert promoted.status_code == 201
            assert promoted.json()["previous_version"] == "feature-baseline-v1"
            failing_experiment = write_experiment(
                "feature-baseline-v1", eligible=False, regressions=["critical-case"]
            )
            assert client.post(
                "/api/v1/prompts/releases/rollback",
                json={**baseline_payload, "experiment_sha256": failing_experiment},
                headers=headers,
            ).status_code == 409
            active = client.get("/api/v1/prompts/releases").json()["active"]
            assert active["version"] == "feature-candidate-v1"
            rollback_experiment = write_experiment("feature-baseline-v1")
            rolled_back = client.post(
                "/api/v1/prompts/releases/rollback",
                json={**baseline_payload, "experiment_sha256": rollback_experiment},
                headers=headers,
            )
            assert rolled_back.status_code == 201
            assert rolled_back.json()["action"] == "rollback"
            active = client.get("/api/v1/prompts/releases").json()["active"]
            assert active["version"] == "feature-baseline-v1"
        with factory() as session:
            releases = session.scalars(select(PromptRelease)).all()
            assert [row.action for row in releases] == ["promote", "promote", "rollback"]
            audit = session.scalars(
                select(AuditRecord).where(AuditRecord.action.like("prompt.%"))
            ).all()
            assert len(audit) == 3
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()
