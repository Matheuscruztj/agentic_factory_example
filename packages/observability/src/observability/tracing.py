"""Optional OpenTelemetry spans that carry IDs and metadata, never prompt data."""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_PROVIDER: TracerProvider | None = None


def configure_tracing(
    endpoint: str | None = None, *, service_name: str = "agentic-factory"
) -> bool:
    """Configure OTLP only when explicitly enabled; exporter errors stay non-fatal."""
    global _PROVIDER
    target = (
        endpoint
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )
    if not target:
        return False
    if not target.startswith(("http://127.0.0.1", "http://localhost", "http://[::1]")):
        return False
    if not target.endswith("/v1/traces"):
        target = target.rstrip("/") + "/v1/traces"
    if _PROVIDER is not None:
        return True
    try:
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=target)))
        trace.set_tracer_provider(provider)
        _PROVIDER = provider
        return True
    except Exception:
        return False


@contextmanager
def workflow_span(
    workflow: str,
    *,
    correlation_id: str,
    task_id: str | None = None,
    attributes: Mapping[str, str | int | float | bool] | None = None,
) -> Iterator[Any]:
    """Create a workflow span and safe span attributes for OpenBot/LangGraph bridges."""
    tracer = trace.get_tracer("agentic_factory.workflow")
    with tracer.start_as_current_span(workflow) as span:
        span.set_attribute("correlation.id", correlation_id)
        if task_id:
            span.set_attribute("task.id", task_id)
        for key, value in (attributes or {}).items():
            if _safe_attribute(key):
                span.set_attribute(key, value)
        yield span


@contextmanager
def model_span(
    model: str,
    *,
    correlation_id: str,
    task_id: str | None = None,
    provider: str = "ollama",
) -> Iterator[Any]:
    """Create a model span with model identity only; prompts and outputs are excluded."""
    with workflow_span(
        "model.call",
        correlation_id=correlation_id,
        task_id=task_id,
        attributes={"gen_ai.request.model": model, "gen_ai.system": provider},
    ) as span:
        yield span


def _safe_attribute(key: str) -> bool:
    lowered = key.lower()
    sensitive = ("prompt", "response", "content", "token", "secret", "password", "authorization")
    return not any(item in lowered for item in sensitive)
