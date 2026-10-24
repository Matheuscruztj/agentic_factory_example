from __future__ import annotations

from pathlib import Path
from uuid import UUID

from customer_registry import main
from fastapi.testclient import TestClient


def payload(
    username: str = "ada-example", name: str = "Ada Example", email: str = "ADA@example.com"
) -> dict[str, str]:
    return {"username": username, "name": name, "email": email}


def test_user_lifecycle_and_case_insensitive_conflicts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REGISTRY_SQLITE_PATH", str(tmp_path / "registry.sqlite3"))
    with TestClient(main.app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").status_code == 200

        created = client.post("/api/v1/users", json=payload())
        assert created.status_code == 201
        user = created.json()
        UUID(user["id"])
        assert user["status"] == "active"

        duplicate_email = client.post(
            "/api/v1/users", json=payload("another-user", "Other", "ada@EXAMPLE.com")
        )
        assert duplicate_email.status_code == 409
        assert duplicate_email.json()["detail"]["code"] == "EMAIL_ALREADY_EXISTS"

        duplicate_username = client.post(
            "/api/v1/users", json=payload("ADA-EXAMPLE", "Other", "other@example.com")
        )
        assert duplicate_username.status_code == 409
        assert duplicate_username.json()["detail"]["code"] == "USERNAME_ALREADY_EXISTS"

        changed = client.patch(f"/api/v1/users/{user['id']}", json={"name": "Ada Lovelace"})
        assert changed.status_code == 200
        assert changed.json()["name"] == "Ada Lovelace"

        missing = client.patch(
            "/api/v1/users/00000000-0000-0000-0000-000000000000", json={"name": "Nobody"}
        )
        assert missing.status_code == 404

        deactivated = client.delete(f"/api/v1/users/{user['id']}")
        assert deactivated.status_code == 204
        assert client.get("/api/v1/users").json() == []
        inactive = client.get("/api/v1/users", params={"include_inactive": "true"}).json()
        assert len(inactive) == 1 and inactive[0]["status"] == "inactive"
        search = client.get(
            "/api/v1/users", params={"include_inactive": "true", "search": "ada-example"}
        )
        assert search.status_code == 200 and len(search.json()) == 1


def test_input_validation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REGISTRY_SQLITE_PATH", str(tmp_path / "registry.sqlite3"))
    with TestClient(main.app) as client:
        invalid = client.post("/api/v1/users", json=payload("x", " ", "invalid"))
        assert invalid.status_code == 422
        empty_patch = client.patch("/api/v1/users/00000000-0000-0000-0000-000000000000", json={})
        assert empty_patch.status_code == 400
