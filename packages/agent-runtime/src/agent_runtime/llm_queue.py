"""Cross-process semaphore for scarce local inference capacity using PostgreSQL locks."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from threading import Event
from time import monotonic, sleep


@contextmanager
def inference_slot(
    connection,
    *,
    max_parallel: int = 1,
    timeout_seconds: float = 900,
    cancelled: Event | None = None,
) -> Iterator[int]:
    """Acquire one of N global PostgreSQL advisory-lock slots; block when saturated."""
    if type(max_parallel) is not int or not 1 <= max_parallel <= 64:
        raise ValueError("INVALID_INFERENCE_CAPACITY")
    if not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds <= 7200:
        raise ValueError("INVALID_INFERENCE_QUEUE_TIMEOUT")
    slot = None
    deadline = monotonic() + timeout_seconds
    while slot is None:
        if cancelled is not None and cancelled.is_set():
            raise InterruptedError("INFERENCE_QUEUE_CANCELLED")
        for candidate in range(max_parallel):
            cursor = connection.execute(
                "SELECT pg_try_advisory_lock(%s, %s)", (0x41464142, candidate)
            )
            if cursor.fetchone()[0]:
                slot = candidate
                break
        if slot is None:
            if monotonic() >= deadline:
                raise TimeoutError("INFERENCE_CAPACITY_TIMEOUT")
            sleep(0.1)
    try:
        yield slot
    finally:
        connection.execute("SELECT pg_advisory_unlock(%s, %s)", (0x41464142, slot))


@asynccontextmanager
async def postgres_inference_slot(
    connection_factory,
    *,
    max_parallel: int = 1,
    timeout_seconds: float = 900,
):
    """Acquire a cross-process GPU slot without blocking the async event loop."""
    connection = await asyncio.to_thread(connection_factory)
    cancelled = Event()
    manager = inference_slot(
        connection,
        max_parallel=max_parallel,
        timeout_seconds=timeout_seconds,
        cancelled=cancelled,
    )
    acquire = asyncio.create_task(asyncio.to_thread(manager.__enter__))
    entered = False
    try:
        slot = await asyncio.shield(acquire)
        entered = True
        yield slot
    except asyncio.CancelledError:
        cancelled.set()
        try:
            await asyncio.shield(acquire)
            entered = True
        except (InterruptedError, TimeoutError):
            pass
        raise
    finally:
        if entered:
            await asyncio.to_thread(manager.__exit__, None, None, None)
        await asyncio.to_thread(connection.close)
