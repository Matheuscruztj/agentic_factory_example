from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from shared_contracts.db import Base
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def database_url() -> str:
    configured = os.getenv("REGISTRY_DATABASE_URL", "").strip()
    if configured:
        return configured
    path = Path(os.getenv("REGISTRY_SQLITE_PATH", ".runtime/customer-registry.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve()}"


@lru_cache(maxsize=8)
def _engine_for(url: str) -> Engine:
    options = {"check_same_thread": False} if url.startswith("sqlite:") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=options)


def get_engine() -> Engine:
    return _engine_for(database_url())


def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def initialize_sqlite() -> None:
    if database_url().startswith("sqlite:"):
        import customer_registry.models  # noqa: F401

        Base.metadata.create_all(get_engine())
