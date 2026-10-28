"""LangGraph construction helpers with mandatory PostgreSQL persistence."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit


@contextmanager
def postgres_checkpointer(database_url: str | None = None) -> Iterator[object]:
    """Yield a configured PostgresSaver; never silently fall back to memory."""
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("LANGGRAPH_POSTGRES_DATABASE_URL_REQUIRED")
    parsed = urlsplit(url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ValueError("LANGGRAPH_POSTGRES_DATABASE_URL_REQUIRED")
    conn_string = urlunsplit(("postgresql", parsed.netloc, parsed.path, parsed.query, ""))
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError as exc:
        raise RuntimeError("INSTALL_AGENT_RUNTIME_WITH_LANGGRAPH_EXTRAS") from exc
    with PostgresSaver.from_conn_string(conn_string) as saver:
        saver.setup()
        yield saver


def compile_durable(graph: object, checkpointer: object) -> Any:
    """Compile with an explicit durable saver, rejecting in-memory savers."""
    if checkpointer.__class__.__name__ in {"InMemorySaver", "MemorySaver"}:
        raise ValueError("IN_MEMORY_CHECKPOINTER_FORBIDDEN")
    compile_graph = getattr(graph, "compile", None)
    if not callable(compile_graph):
        raise TypeError("LANGGRAPH_BUILDER_REQUIRED")
    return compile_graph(checkpointer=checkpointer)


@asynccontextmanager
async def async_postgres_checkpointer(database_url: str) -> AsyncIterator[object]:
    """Async operational graphs require the async saver, never a memory fallback."""
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ValueError("LANGGRAPH_POSTGRES_DATABASE_URL_REQUIRED")
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    conn_string = urlunsplit(("postgresql", parsed.netloc, parsed.path, parsed.query, ""))
    os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")
    async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
        await saver.setup()
        yield saver
