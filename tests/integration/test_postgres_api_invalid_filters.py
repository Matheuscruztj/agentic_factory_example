from __future__ import annotations

from dataclasses import replace

from customer_registry.main import app as registry_app
from factory_api import main as factory_main
from fastapi.testclient import TestClient


def test_invalid_filters_are_rejected_before_postgres_queries(monkeypatch) -> None:
    """Malformed NUL filters must return 422 even against an empty PostgreSQL schema."""
    monkeypatch.setattr(
        factory_main, "settings", replace(factory_main.settings, auth_enabled=False)
    )
    with TestClient(factory_main.app) as factory:
        responses = [
            factory.get("/api/v1/demands", params={"status": "bad\x00value"}),
            factory.get("/api/v1/tasks", params={"status": "bad\x00value"}),
            factory.get("/api/v1/tasks", params={"demand_id": "bad\x00value"}),
        ]
    with TestClient(registry_app) as registry:
        responses.append(
            registry.get("/api/v1/users", params={"search": "bad\x00value"})
        )

    assert [response.status_code for response in responses] == [422, 422, 422, 422]
    assert all(response.headers["x-content-type-options"] == "nosniff" for response in responses)
