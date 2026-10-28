from dataclasses import replace

from customer_registry import main as registry_main
from factory_api import main as factory_main
from factory_api.database import get_db
from fastapi.testclient import TestClient
from shared_contracts.db import Base
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from task_engine.models import AuditRecord


def test_phone_api_and_task_dependency_audit_are_fullstack_and_synthetic(tmp_path, monkeypatch):
    monkeypatch.delenv("REGISTRY_DATABASE_URL", raising=False)
    monkeypatch.setenv("REGISTRY_SQLITE_PATH", str(tmp_path / "registry.sqlite3"))
    with TestClient(registry_main.app) as registry:
        created = registry.post(
            "/api/v1/users",
            json={
                "username": "phone-demo",
                "name": "Demo Person",
                "email": "demo-phone@example.com",
                "phone": "+55 85 99999-0000",
            },
        )
        assert created.status_code == 201
        user = created.json()
        assert user["phone"] == "+55 85 99999-0000"
        updated = registry.patch(
            f"/api/v1/users/{user['id']}", json={"phone": "+55 85 98888-0000"}
        )
        assert updated.json()["phone"] == "+55 85 98888-0000"
        found = registry.get("/api/v1/users", params={"search": "98888"}).json()
        assert found[0]["id"] == user["id"]

    engine = create_engine(f"sqlite:///{tmp_path / 'factory.sqlite3'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with factory() as session:
            yield session

    monkeypatch.setattr(
        factory_main, "settings", replace(factory_main.settings, auth_enabled=False)
    )
    factory_main.app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(factory_main.app) as factory_client:
            demand = factory_client.post(
                "/api/v1/demands",
                json={
                    "source": "manual",
                    "external_id": "demo-phone-088",
                    "title": "Phone demo",
                    "demand_type": "feature",
                    "requirement": "Add optional phone to synthetic registry records",
                    "acceptance": ["API and UI accept and edit phone"],
                },
            ).json()
            first = factory_client.post(
                f"/api/v1/demands/{demand['id']}/tasks",
                json={
                    "title": "API phone field",
                    "owner_role": "backend",
                    "acceptance": ["API persists phone"],
                },
            ).json()
            second = factory_client.post(
                f"/api/v1/demands/{demand['id']}/tasks",
                json={
                    "title": "UI phone field",
                    "owner_role": "frontend",
                    "dependencies": [first["id"]],
                    "acceptance": ["UI submits phone"],
                },
            ).json()
            assert second["dependencies"] == [first["id"]]
        with factory() as session:
            audit = session.scalar(
                select(AuditRecord).where(AuditRecord.subject_id == second["id"])
            )
            assert audit is not None
            assert audit.details["dependencies"] == [first["id"]]
    finally:
        factory_main.app.dependency_overrides.clear()
        engine.dispose()
