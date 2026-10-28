"""Local Ollama request measurements without retaining prompts or responses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class OllamaMeasurement:
    model: str
    requested_at: str
    completed_at: str
    queue_wait_ms: float | None
    load_ms: float | None
    generation_ms: float | None
    total_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    eval_count: int | None
    success: bool
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def measurement_from_response(
    model: str,
    response: dict[str, Any],
    *,
    request_started: float,
    response_received: float,
    queue_started: float | None = None,
    queue_acquired: float | None = None,
) -> OllamaMeasurement:
    """Convert Ollama timing/token fields; absent measurements remain null, never zero."""
    total_ms = max(0.0, (response_received - request_started) * 1000)
    load_ns = response.get("load_duration")
    generation_ns = response.get("eval_duration")
    prompt_eval_ns = response.get("prompt_eval_duration")
    queue_wait_ms = (
        (queue_acquired - queue_started) * 1000
        if queue_started is not None and queue_acquired is not None
        else None
    )
    load_ms = float(load_ns) / 1_000_000 if isinstance(load_ns, (int, float)) else None
    generation_ms = (
        float(generation_ns) / 1_000_000
        if isinstance(generation_ns, (int, float))
        else None
    )
    return OllamaMeasurement(
        model=model,
        requested_at=datetime.fromtimestamp(request_started, UTC).isoformat(),
        completed_at=datetime.fromtimestamp(response_received, UTC).isoformat(),
        queue_wait_ms=queue_wait_ms,
        load_ms=(
            load_ms
            if load_ms is not None
            else float(prompt_eval_ns) / 1_000_000
            if isinstance(prompt_eval_ns, (int, float))
            else None
        ),
        generation_ms=generation_ms,
        total_ms=total_ms,
        prompt_tokens=_count(response.get("prompt_eval_count")),
        completion_tokens=_count(response.get("eval_count")),
        eval_count=_count(response.get("eval_count")),
        success=True,
    )


def failed_measurement(
    model: str, *, request_started: float, response_received: float, error: Exception
) -> OllamaMeasurement:
    """Record only an error type; exception messages can contain user data or credentials."""
    return OllamaMeasurement(
        model=model,
        requested_at=datetime.fromtimestamp(request_started, UTC).isoformat(),
        completed_at=datetime.fromtimestamp(response_received, UTC).isoformat(),
        queue_wait_ms=None, load_ms=None, generation_ms=None,
        total_ms=max(0.0, (response_received - request_started) * 1000),
        prompt_tokens=None, completion_tokens=None, eval_count=None,
        success=False, error_type=type(error).__name__,
    )


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
