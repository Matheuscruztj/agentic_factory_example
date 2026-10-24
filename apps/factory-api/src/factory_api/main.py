"""Factory API liveness, readiness, local auth and sanitized service status."""

from __future__ import annotations

import os
import socket
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from factory_api.auth.session import create_session, verify_password, verify_session
from factory_api.config import Settings
from factory_api.database import engine
from factory_api.operator import require_operator
from factory_api.routers.approvals import router as approvals_router
from factory_api.routers.demands import router as demands_router
from factory_api.routers.demands import tasks_router
from factory_api.routers.events import router as events_router

settings = Settings.from_env()
login_failures: dict[str, deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auth_enabled and (len(settings.secret_key) < 32 or not settings.password_hash):
        raise RuntimeError(
            "Local authentication is enabled; initialize .env with scripts/setup_local_env.py"
        )
    yield


app = FastAPI(title="Agentic Factory API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "FACTORY_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
    ).split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

app.include_router(demands_router)
app.include_router(tasks_router)
app.include_router(approvals_router)
app.include_router(events_router)


class LoginPayload(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE"}) from None
    return {"status": "ready", "dependencies": {"database": "ready"}}


@app.post("/api/v1/auth/login", tags=["auth"])
def login(payload: LoginPayload, response: Response) -> dict:
    if not settings.auth_enabled:
        return {"authenticated": True, "csrf_token": "disabled"}
    attempts = login_failures["local-operator"]
    now = time.monotonic()
    while attempts and now - attempts[0] > 300:
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail={"code": "LOGIN_RATE_LIMITED"})
    if not verify_password(payload.password, settings.password_hash):
        attempts.append(now)
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS"})
    attempts.clear()
    token, csrf = create_session(settings.secret_key)
    response.set_cookie(
        "factory_session",
        token,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=3600,
        path="/",
    )
    return {"authenticated": True, "csrf_token": csrf}


@app.post("/api/v1/auth/logout", dependencies=[Depends(require_operator)], tags=["auth"])
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("factory_session", path="/")
    return {"authenticated": False}


@app.get("/api/v1/auth/session", tags=["auth"])
def session_status(factory_session: str | None = Cookie(default=None)) -> dict:
    if not settings.auth_enabled:
        return {"authenticated": True, "auth_enabled": False}
    data = verify_session(settings.secret_key, factory_session or "")
    return {
        "authenticated": data is not None,
        "auth_enabled": True,
        "csrf_token": data.get("csrf") if data else None,
    }


def check_port(host: str, port: int) -> str:
    try:
        with socket.create_connection((host, port), timeout=1):
            return "available"
    except OSError:
        return "unavailable"


def check_http(url: str) -> str:
    try:
        with urlopen(url, timeout=1.5) as response:
            return "available" if 200 <= response.status < 300 else "unavailable"
    except (URLError, TimeoutError, OSError):
        return "unavailable"


def integration_status(name: str) -> str:
    enabled = os.getenv(f"{name.upper()}_ENABLED", "false").lower() in {"true", "1", "yes"}
    if not enabled:
        return "disabled"
    required = {
        "github": ("GITHUB_OWNER", "GITHUB_REPO"),
        "openbot": ("OPENBOT_BASE_URL", "OPENBOT_API_KEY"),
        "telegram": ("TELEGRAM_BOT_TOKEN",),
        "jira": ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"),
    }[name]
    return "configured" if all(os.getenv(key, "").strip() for key in required) else "misconfigured"


@app.get("/api/v1/config/status", dependencies=[Depends(require_operator)], tags=["status"])
def config_status() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            database_status = "ready"
    except SQLAlchemyError:
        database_status = "unavailable"
    ollama_enabled = os.getenv("OLLAMA_ENABLED", "false").lower() in {"true", "1"}
    return {
        "services": {
            "database": database_status,
            "redis": check_port("127.0.0.1", 6379) if settings.redis_enabled else "disabled",
            "customer_registry": check_http(settings.registry_api_url + "/health/ready"),
            "ollama": check_http(settings.ollama_url + "/api/tags")
            if ollama_enabled
            else "disabled",
        },
        "integrations": {
            name: integration_status(name) for name in ("github", "openbot", "telegram", "jira")
        },
        "secrets_exposed": False,
    }
