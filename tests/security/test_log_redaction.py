import json
import logging

from observability.logging import CorrelationContext, JsonFormatter
from observability.redaction import redact_fields, redact_text


def test_redaction_masks_secret_fields_and_embedded_credentials():
    fields = redact_fields({
        "access_token": "bearer-secret",
        "message": (
            "Authorization: Bearer abc.def password=hunter2 jwt "
            "eyJabcdefghijk.abcdefghijk.abcdefghijk"
        ),
        "nested": {"api_key": "k-123", "ok": "fine"},
    })
    encoded = json.dumps(fields)
    assert "bearer-secret" not in encoded
    assert "abc.def" not in encoded
    assert "hunter2" not in encoded
    assert "eyJabcdefghijk" not in encoded
    assert fields["access_token"] == "[REDACTED]"
    assert fields["nested"]["api_key"] == "[REDACTED]"
    assert redact_text("Bearer raw-token") == "Bearer [REDACTED]"


def test_correlation_context_and_formatter_are_traceable_and_safe():
    context = CorrelationContext("corr-123")
    context.bind_task("task-456")
    assert context.fields() == {"correlation_id": "corr-123", "task_id": "task-456"}

    record = logging.LogRecord("test", logging.INFO, "", 1, "token=raw-secret", (), None)
    formatted = JsonFormatter().format(record)
    assert "raw-secret" not in formatted
    assert json.loads(formatted)["message"] == "token=[REDACTED]"
