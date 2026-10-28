import hashlib
import hmac
import json
from dataclasses import replace
from uuid import uuid4

from factory_api import main
from factory_api.database import get_db
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import Demand, Task


def test_github_webhook_signature_idempotency_and_no_execution(tmp_path, monkeypatch):
    secret = "local-webhook-secret"
    raw = json.dumps({
        "action": "opened",
        "issue": {"number": 17, "title": "Synthetic issue", "body": "untrusted issue body"},
        "repository": {"full_name": "example/demo"},
    }, separators=(",", ":")).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    engine = create_engine(f"sqlite:///{tmp_path / 'webhook.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("GITHUB_ALLOWED_REPOSITORIES", "example/demo")
    main.app.dependency_overrides[get_db] = override_db
    delivery = str(uuid4())
    headers = {
        "X-Hub-Signature-256": signature,
        "X-GitHub-Event": "issues",
        "X-GitHub-Delivery": delivery,
        "Content-Type": "application/json",
    }
    try:
        with TestClient(main.app) as client:
            invalid_headers = {**headers, "X-Hub-Signature-256": "sha256=" + "0" * 64}
            rejected = client.post(
                "/api/v1/webhooks/github", content=raw, headers=invalid_headers
            )
            assert rejected.status_code == 401
            accepted = client.post("/api/v1/webhooks/github", content=raw, headers=headers)
            replay = client.post("/api/v1/webhooks/github", content=raw, headers=headers)
            assert accepted.status_code == 200 and accepted.json()["execution_started"] is False
            assert replay.json()["duplicate"] is True

            untrusted_raw = json.dumps(
                {
                    "action": "opened",
                    "issue": {"number": 18, "title": "Untrusted repository"},
                    "repository": {"full_name": "attacker/other"},
                },
                separators=(",", ":"),
            ).encode()
            untrusted_signature = "sha256=" + hmac.new(
                secret.encode(), untrusted_raw, hashlib.sha256
            ).hexdigest()
            forbidden = client.post(
                "/api/v1/webhooks/github",
                content=untrusted_raw,
                headers={
                    **headers,
                    "X-Hub-Signature-256": untrusted_signature,
                    "X-GitHub-Delivery": str(uuid4()),
                },
            )
            assert forbidden.status_code == 403
            assert forbidden.json()["detail"]["code"] == "WEBHOOK_REPOSITORY_FORBIDDEN"
        with factory() as session:
            assert len(session.scalars(select(Demand)).all()) == 1
            assert session.scalars(select(Task)).all() == []
    finally:
        main.app.dependency_overrides.clear()
        engine.dispose()
