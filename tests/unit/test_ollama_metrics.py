from observability import ollama_client
from observability.ollama_metrics import failed_measurement, measurement_from_response


def test_ollama_metrics_separate_wait_load_generation_and_tokens():
    result = measurement_from_response(
        "local-model",
        {
            "load_duration": 2_000_000,
            "prompt_eval_duration": 5_000_000,
            "eval_duration": 11_000_000,
            "prompt_eval_count": 40,
            "eval_count": 12,
            "prompt": "must not be recorded",
            "response": "must not be recorded",
        },
        request_started=100.0,
        response_received=100.1,
        queue_started=99.5,
        queue_acquired=100.0,
    )
    assert result.queue_wait_ms == 500
    assert result.load_ms == 2
    assert result.generation_ms == 11
    assert result.prompt_tokens == 40
    assert result.completion_tokens == 12
    assert "must not be recorded" not in str(result.to_dict())


def test_missing_metrics_and_errors_are_non_blocking_and_sanitized():
    result = measurement_from_response(
        "local-model", {}, request_started=20, response_received=20.25
    )
    assert result.load_ms is None
    assert result.prompt_tokens is None
    failed = failed_measurement(
        "local-model", request_started=20, response_received=20.25,
        error=RuntimeError("token=private credential"),
    )
    assert failed.success is False
    assert failed.error_type == "RuntimeError"
    assert "private" not in str(failed.to_dict())


def test_telemetry_recorder_failure_does_not_hide_success(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "ok", "eval_count": 1}

    monkeypatch.setattr(ollama_client.httpx, "post", lambda *args, **kwargs: Response())
    result = ollama_client.generate(
        "local-model",
        "prompt",
        recorder=lambda _measurement: (_ for _ in ()).throw(RuntimeError("metrics down")),
    )
    assert result["response"] == "ok"
