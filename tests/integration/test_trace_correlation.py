import json
import logging

from observability import tracing
from observability.logging import CorrelationContext, JsonFormatter


def test_trace_fields_survive_structured_logging_without_secrets():
    context = CorrelationContext("corr-workflow-1", "task-123")
    record = logging.LogRecord("workflow", logging.INFO, "", 1, "tool completed", (), None)
    record.fields = {**context.fields(), "model": "local-model", "authorization": "Bearer secret"}
    rendered = JsonFormatter().format(record)
    assert "secret" not in rendered
    event = json.loads(rendered)
    assert event["correlation_id"] == "corr-workflow-1"
    assert event["task_id"] == "task-123"


def test_collector_off_remains_a_valid_telemetry_free_configuration():
    # Collector is opt-in in Compose; clients with no exporter still emit local JSON only.
    context = CorrelationContext("offline-trace")
    assert context.fields()["correlation_id"] == "offline-trace"


def test_workflow_and_model_spans_keep_correlation_but_reject_content_attributes(monkeypatch):
    class Span:
        def __init__(self):
            self.attributes = {}

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Tracer:
        def start_as_current_span(self, _name):
            return Span()

    monkeypatch.setattr(tracing.trace, "get_tracer", lambda _name: Tracer())
    with tracing.workflow_span(
        "workflow.run",
        correlation_id="corr-1",
        task_id="task-1",
        attributes={"workflow.stage": "implement", "input.prompt": "secret"},
    ) as span:
        assert span.attributes == {
            "correlation.id": "corr-1",
            "task.id": "task-1",
            "workflow.stage": "implement",
        }
    with tracing.model_span("local-model", correlation_id="corr-2") as span:
        assert span.attributes["gen_ai.request.model"] == "local-model"


def test_exporter_configuration_is_local_only_and_uses_trace_endpoint(monkeypatch):
    endpoints = []

    class FakeProvider:
        def __init__(self, **_kwargs):
            pass

        def add_span_processor(self, _processor):
            return None

    class FakeExporter:
        def __init__(self, *, endpoint):
            endpoints.append(endpoint)

    monkeypatch.setattr(tracing, "_PROVIDER", None)
    monkeypatch.setattr(tracing, "TracerProvider", FakeProvider)
    monkeypatch.setattr(tracing, "OTLPSpanExporter", FakeExporter)
    monkeypatch.setattr(tracing, "BatchSpanProcessor", lambda exporter: exporter)
    monkeypatch.setattr(tracing.trace, "set_tracer_provider", lambda _provider: None)
    assert tracing.configure_tracing("http://127.0.0.1:4318") is True
    assert endpoints == ["http://127.0.0.1:4318/v1/traces"]
    monkeypatch.setattr(tracing, "_PROVIDER", None)
    assert tracing.configure_tracing("https://collector.example/v1/traces") is False
