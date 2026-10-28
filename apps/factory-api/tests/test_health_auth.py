from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from factory_api import main
from factory_api.auth.session import create_session, verify_password, verify_session
from fastapi.testclient import TestClient
from sqlalchemy import create_engine


def test_liveness_readiness_and_config_redaction(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'factory.db'}")
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    monkeypatch.setenv("GITHUB_ENABLED", "true")
    monkeypatch.delenv("GITHUB_OWNER", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    monkeypatch.setenv("GITHUB_AUTH_MODE", "pat")
    monkeypatch.setenv("GITHUB_TOKEN", "do-not-return-this-value")
    with TestClient(main.app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").status_code == 200
        headers = client.get("/health/live").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        result = client.get("/api/v1/config/status").json()
        assert result["secrets_exposed"] is False
        assert "password" not in str(result).lower()
        assert result["integrations"]["github"] == "configured"
        assert "do-not-return-this-value" not in str(result)
    engine.dispose()


def test_demand_and_task_filters_reject_malformed_values(monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    with TestClient(main.app) as client:
        assert client.get("/api/v1/demands", params={"status": "bad\x00value"}).status_code == 422
        assert client.get("/api/v1/demands", params={"status": "bad-status"}).status_code == 422
        assert client.get(
            "/api/v1/tasks", params={"status": "bad\x00value"}
        ).status_code == 422
        assert client.get("/api/v1/tasks", params={"status": "bad-status"}).status_code == 422
        assert client.get(
            "/api/v1/tasks", params={"demand_id": "bad\x00value"}
        ).status_code == 422


def test_request_correlation_id_is_returned_and_invalid_input_is_replaced(monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))
    with TestClient(main.app) as client:
        accepted = client.get("/health/live", headers={"X-Correlation-ID": "task:123"})
        assert accepted.headers["X-Correlation-ID"] == "task:123"
        replaced = client.get("/health/live", headers={"X-Correlation-ID": "bad\r\nvalue"})
        assert replaced.status_code == 200
        assert replaced.headers["X-Correlation-ID"] != "bad\r\nvalue"


def test_login_sets_http_only_cookie_and_guards_status(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'factory.db'}")
    password_hash = (
        "scrypt:16384:8:1:73616c74:"
        + hashlib.scrypt(b"correct horse", salt=b"salt", n=16384, r=8, p=1, dklen=32).hex()
    )
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(
        main,
        "settings",
        replace(main.settings, auth_enabled=True, secret_key="s" * 40, password_hash=password_hash),
    )
    with TestClient(main.app) as client:
        assert client.get("/api/v1/config/status").status_code == 401
        invalid = client.post("/api/v1/auth/login", json={"password": "wrong"})
        assert invalid.status_code == 401
        logged_in = client.post("/api/v1/auth/login", json={"password": "correct horse"})
        assert logged_in.status_code == 200
        assert logged_in.headers.get("set-cookie", "").lower().find("httponly") >= 0
        assert client.get("/api/v1/config/status").status_code == 200
        assert client.post("/api/v1/auth/logout").status_code == 403
        assert (
            client.post(
                "/api/v1/auth/logout", headers={"X-CSRF-Token": logged_in.json()["csrf_token"]}
            ).status_code
            == 200
        )
        assert client.get("/api/v1/config/status").status_code == 401
    engine.dispose()


def test_signed_session_and_password_hash() -> None:
    encoded = (
        "scrypt:16384:8:1:73616c74:"
        + hashlib.scrypt(b"correct horse", salt=b"salt", n=16384, r=8, p=1, dklen=32).hex()
    )
    assert verify_password("correct horse", encoded)
    assert not verify_password("wrong", encoded)
    token, csrf = create_session("x" * 40)
    session = verify_session("x" * 40, token)
    assert session and session["csrf"] == csrf
    assert verify_session("y" * 40, token) is None
