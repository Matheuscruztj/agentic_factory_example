from __future__ import annotations

import json

import pytest

from scripts import compare_gateway


def test_abba_benchmark_records_identical_route_samples_and_inconclusive_small_n(
    tmp_path, monkeypatch
):
    calls = []

    def fake_call(_client, route, _model, _prompt, _key, _direct_url, _proxy_url):
        calls.append(route)
        return {
            "route": route,
            "latency_ms": 10.0 if route == "direct" else 12.0,
            "prompt_tokens": 4,
            "completion_tokens": 1,
            "response_chars": 2,
            "error_class": None,
        }

    monkeypatch.setattr(compare_gateway, "_call", fake_call)
    output = tmp_path / "report.json"
    report = compare_gateway.run(repeats=2, model="local-model", key="sk-local", output=output)
    assert calls == [
        "direct",
        "proxy",
        "direct",
        "proxy",
        "proxy",
        "direct",
        "proxy",
        "direct",
        "direct",
        "proxy",
    ]
    assert report["status"] == "inconclusive_insufficient_pairs"
    assert report["conclusion"] is None
    assert report["metrics"]["proxy"]["p50_ms"] == 12.0
    assert json.loads(output.read_text())["samples_per_route"] == {"direct": 4, "proxy": 4}


def test_benchmark_rejects_invalid_repetitions_before_inference(tmp_path):
    with pytest.raises(ValueError, match="REPEATS_OUT_OF_RANGE"):
        compare_gateway.run(repeats=0, model="local-model", key="sk-local", output=tmp_path / "x")


@pytest.mark.parametrize("route", ["direct", "proxy"])
def test_gateway_probe_bounds_and_pairs_sampling_parameters(route):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            if route == "direct":
                return {"message": {"content": "OK"}, "prompt_eval_count": 2, "eval_count": 1}
            return {
                "choices": [{"message": {"content": "OK"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            }

    class Client:
        payload = None

        def post(self, url, **kwargs):
            self.payload = kwargs["json"]
            return Response()

    client = Client()
    compare_gateway._call(
        client, route, "qwen3:4b", "same prompt", "sk-local", "http://ollama:11434",
        "http://127.0.0.1:4000",
    )
    body = client.payload
    if route == "direct":
        assert body["think"] is False
        assert body["options"] == {"temperature": 0, "num_predict": 32}
    else:
        assert body["temperature"] == 0
        assert body["max_tokens"] == 32
        assert body["reasoning_effort"] == "minimal"


def test_five_pairs_report_metrics_without_inventing_a_winner(tmp_path, monkeypatch):
    def fake_call(_client, route, _model, _prompt, _key, _direct, _proxy):
        return {"route": route, "latency_ms": 10.0 if route == "direct" else 11.0,
                "prompt_tokens": 2, "completion_tokens": 1, "response_chars": 2,
                "error_class": None}

    monkeypatch.setattr(compare_gateway, "_call", fake_call)
    report = compare_gateway.run(repeats=5, model="local-model", key="sk-local",
                                 output=tmp_path / "five.json")
    assert report["status"] == "complete"
    assert report["samples_per_route"] == {"direct": 10, "proxy": 10}
    assert report["metrics"]["direct"]["p50_ms"] == 10.0
    assert report["metrics"]["proxy"]["p95_ms"] == 11.0
    assert report["conclusion"] is None
