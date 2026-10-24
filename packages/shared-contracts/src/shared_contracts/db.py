"""SQLAlchemy database configuration and request-scoped sessions."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_session_factory(url: str | None = None) -> sessionmaker[Session]:
    database_url = url or os.getenv("DATABASE_URL", "sqlite:///./.runtime/factory.db")
    if database_url.startswith("sqlite:///"):
        from pathlib import Path

        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_dependency(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
