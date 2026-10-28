"""Non-blocking Ollama instrumentation wrapper using the local HTTP API."""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from observability.logging import log_record
from observability.ollama_metrics import failed_measurement, measurement_from_response


def generate(
    model: str,
    prompt: str,
    *,
    base_url: str = "http://127.0.0.1:11434",
    timeout_seconds: float = 180,
    queue_timing: tuple[float, float] | None = None,
    recorder: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Generate a response and emit telemetry; errors in telemetry never fail the call."""
    wall_start = datetime.now(UTC).timestamp()
    monotonic_start = time.monotonic()
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout_seconds,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        ended = time.monotonic()
        measurement = measurement_from_response(
            model,
            payload,
            request_started=wall_start,
            response_received=wall_start + ended - monotonic_start,
            queue_started=queue_timing[0] if queue_timing else None,
            queue_acquired=queue_timing[1] if queue_timing else None,
        )
    except Exception as exc:
        measurement = failed_measurement(
            model,
            request_started=wall_start,
            response_received=wall_start + time.monotonic() - monotonic_start,
            error=exc,
        )
        _record(measurement.to_dict(), recorder)
        raise
    _record(measurement.to_dict(), recorder)
    return payload


def _record(
    measurement: dict[str, Any], recorder: Callable[[dict[str, Any]], None] | None
) -> None:
    try:
        if recorder is not None:
            recorder(measurement)
        else:
            artifact = Path(
                os.getenv("FACTORY_METRICS_PATH", ".runtime/observability/ollama.jsonl")
            )
            artifact.parent.mkdir(parents=True, exist_ok=True)
            with artifact.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(measurement, separators=(",", ":")) + "\n")
            log_record(
                logging.getLogger("observability.ollama"),
                logging.INFO,
                "ollama.generation",
                **measurement,
            )
    except Exception:
        # Telemetry cannot turn a working model call into a failed task.
        return
