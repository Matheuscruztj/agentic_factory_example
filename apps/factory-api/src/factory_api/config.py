"""Environment-backed settings with safe local defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str = "local"
    secret_key: str = ""
    password_hash: str = ""
    auth_enabled: bool = True
    database_url: str = "sqlite:///.runtime/factory.db"
    registry_api_url: str = "http://127.0.0.1:8010"
    ollama_url: str = "http://127.0.0.1:11434"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_enabled: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            environment=os.getenv("FACTORY_ENV", "local"),
            secret_key=os.getenv("APP_SECRET_KEY", ""),
            password_hash=os.getenv("OPERATOR_PASSWORD_HASH", ""),
            auth_enabled=os.getenv("LOCAL_AUTH_ENABLED", "true").lower() in {"true", "1", "yes"},
            database_url=os.getenv("DATABASE_URL", "sqlite:///.runtime/factory.db"),
            registry_api_url=os.getenv("REGISTRY_API_URL", "http://127.0.0.1:8010"),
            ollama_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            redis_enabled=os.getenv("REDIS_ENABLED", "false").lower() in {"true", "1", "yes"},
        )
