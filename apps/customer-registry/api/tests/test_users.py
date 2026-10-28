from __future__ import annotations

from pathlib import Path
from uuid import UUID

from customer_registry import main
from fastapi.testclient import TestClient


def payload(
    username: str = "ada-example", name: str = "Ada Example", email: str = "ADA@example.com",
    phone: str | None = None,
) -> dict[str, str]:
    result = {"username": username, "name": name, "email": email}
    if phone is not None:
        result["phone"] = phone
    return result


def test_user_lifecycle_and_case_insensitive_conflicts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("REGISTRY_DATABASE_URL", raising=False)
    monkeypatch.setenv("REGISTRY_SQLITE_PATH", str(tmp_path / "registry.sqlite3"))
    with TestClient(main.app) as client:
        live = client.get("/health/live")
        assert live.json() == {"status": "ok"}
        assert live.headers["X-Content-Type-Options"] == "nosniff"
        assert live.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in live.headers["Content-Security-Policy"]
        assert client.get("/health/ready").status_code == 200

        created = client.post("/api/v1/users", json=payload())
        assert created.status_code == 201
        user = created.json()
        UUID(user["id"])
        assert user["status"] == "active"

        with_phone = client.post(
            "/api/v1/users",
            json=payload(
                "phone-user", "Phone User", "phone@example.com", "+55 85 99999-0000"
            ),
        )
        assert with_phone.status_code == 201
        phone_user = with_phone.json()
        assert phone_user["phone"] == "+55 85 99999-0000"
        changed_phone = client.patch(
            f"/api/v1/users/{phone_user['id']}", json={"phone": "+55 85 98888-0000"}
        )
        assert changed_phone.json()["phone"] == "+55 85 98888-0000"
        omitted_phone = client.patch(
            f"/api/v1/users/{phone_user['id']}", json={"name": "Phone User Updated"}
        )
        assert omitted_phone.status_code == 200
        assert omitted_phone.json()["phone"] == "+55 85 98888-0000"
        cleared_phone = client.patch(f"/api/v1/users/{phone_user['id']}", json={"phone": None})
        assert cleared_phone.status_code == 200 and cleared_phone.json()["phone"] is None
        restored_phone = client.patch(
            f"/api/v1/users/{phone_user['id']}", json={"phone": "+55 85 99999-0000"}
        )
        assert restored_phone.status_code == 200
        assert client.patch(
            f"/api/v1/users/{phone_user['id']}", json={"phone": ""}
        ).status_code == 422
        assert client.patch(
            f"/api/v1/users/{phone_user['id']}", json={"phone": "call me"}
        ).status_code == 422
        assert client.delete(f"/api/v1/users/{phone_user['id']}").status_code == 204

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
        assert len(inactive) == 2 and all(user["status"] == "inactive" for user in inactive)
        search = client.get(
            "/api/v1/users", params={"include_inactive": "true", "search": "ada-example"}
        )
        assert search.status_code == 200 and len(search.json()) == 1
        assert client.get("/api/v1/users", params={"search": "bad\x00value"}).status_code == 422


def test_input_validation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("REGISTRY_DATABASE_URL", raising=False)
    monkeypatch.setenv("REGISTRY_SQLITE_PATH", str(tmp_path / "registry.sqlite3"))
    with TestClient(main.app) as client:
        invalid = client.post("/api/v1/users", json=payload("x", " ", "invalid"))
        assert invalid.status_code == 422
        invalid_phone = client.post(
            "/api/v1/users",
            json=payload("bad-phone", "Bad Phone", "bad-phone@example.com", "call-me"),
        )
        assert invalid_phone.status_code == 422
        empty_patch = client.patch("/api/v1/users/00000000-0000-0000-0000-000000000000", json={})
        assert empty_patch.status_code == 400


def test_shared_tag_catalog_assignment_filter_and_removal(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("REGISTRY_DATABASE_URL", raising=False)
    monkeypatch.setenv("REGISTRY_SQLITE_PATH", str(tmp_path / "tag-registry.sqlite3"))
    with TestClient(main.app) as client:
        label = client.post("/api/v1/tags", json={"name": "  VIP  "})
        assert label.status_code == 201 and label.json()["name"] == "VIP"
        assert client.post("/api/v1/tags", json={"name": "vip"}).status_code == 409
        accent = client.post("/api/v1/tags", json={"name": "Víp"})
        assert accent.status_code == 201  # casefold does not strip accents
        assert client.post("/api/v1/tags", json={"name": "   "}).status_code == 422
        invalid_create = client.post(
            "/api/v1/users",
            json={**payload("invalid-tag", "Invalid Tag", "invalid-tag@example.com"),
                  "tag_ids": ["00000000-0000-0000-0000-000000000000"]},
        )
        assert invalid_create.status_code == 422
        assert client.get("/api/v1/users").json() == []

        created = client.post(
            "/api/v1/users",
            json={**payload(), "tag_ids": [label.json()["id"]]},
        )
        assert created.status_code == 201
        user = created.json()
        assert [tag["id"] for tag in user["tags"]] == [label.json()["id"]]
        assert len(client.get("/api/v1/users", params={"tag_id": label.json()["id"]}).json()) == 1
        assert client.get("/api/v1/users", params={"tag_id": accent.json()["id"]}).json() == []
        # Omitted and null tag_ids preserve the association; [] explicitly clears it.
        unchanged = client.patch(f"/api/v1/users/{user['id']}", json={"name": "Ada Updated"})
        assert unchanged.status_code == 200
        assert [tag["id"] for tag in unchanged.json()["tags"]] == [label.json()["id"]]
        null_tags = client.patch(
            f"/api/v1/users/{user['id']}", json={"name": "Ada Again", "tag_ids": None}
        )
        assert null_tags.status_code == 200
        assert [tag["id"] for tag in null_tags.json()["tags"]] == [label.json()["id"]]
        assert client.patch(f"/api/v1/users/{user['id']}", json={"tag_ids": []}).status_code == 200
        assert client.get("/api/v1/tags").json() == [label.json(), accent.json()]
        assert client.get("/api/v1/users", params={"tag_id": label.json()["id"]}).json() == []

        ten_tags = [
            client.post("/api/v1/tags", json={"name": f"label-{n}"}).json()["id"]
            for n in range(10)
        ]
        too_many = client.patch(
            f"/api/v1/users/{user['id']}",
            json={"tag_ids": ten_tags + [label.json()["id"]]},
        )
        assert too_many.status_code == 422
        assert client.patch(
            f"/api/v1/users/{user['id']}", json={"tag_ids": [label.json()["id"]]}
        ).status_code == 200
        duplicate_ids = client.patch(
            f"/api/v1/users/{user['id']}",
            json={"name": "Must Also Roll Back", "tag_ids": [ten_tags[0], ten_tags[0]]},
        )
        assert duplicate_ids.status_code == 422
        unknown = client.patch(
            f"/api/v1/users/{user['id']}",
            json={"name": "Must Roll Back", "tag_ids": ["00000000-0000-0000-0000-000000000000"]},
        )
        assert unknown.status_code == 422
        unchanged = client.get("/api/v1/users", params={"include_inactive": "true"}).json()[0]
        assert unchanged["name"] == "Ada Again"
        assert [tag["id"] for tag in unchanged["tags"]] == [label.json()["id"]]
