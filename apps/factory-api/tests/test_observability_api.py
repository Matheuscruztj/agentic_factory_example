import json
from dataclasses import replace

import pytest
from factory_api import main
from factory_api.routers import observability
from fastapi.testclient import TestClient


def test_observability_summary_filters_and_separates_measured_from_estimated(tmp_path, monkeypatch):
    metrics = tmp_path / "ollama.jsonl"
    metrics.write_text(
        "\n".join([
            json.dumps({"task_id": "task-a", "success": True, "total_ms": 10,
                        "queue_wait_ms": 2, "load_ms": 1, "generation_ms": 5,
                        "prompt_tokens": 7, "completion_tokens": 3}),
            json.dumps({"task_id": "task-b", "success": False, "total_ms": 50,
                        "queue_wait_ms": 8, "load_ms": None, "generation_ms": None,
                        "prompt_tokens": None, "completion_tokens": None}),
        ]),
        encoding="utf-8",
    )
    hardware = tmp_path / "hardware.json"
    hardware.write_text(json.dumps({"status": "available", "devices": []}), encoding="utf-8")
    monkeypatch.setattr(observability, "_METRICS", metrics)
    monkeypatch.setattr(observability, "_HARDWARE", hardware)
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))

    with TestClient(main.app) as client:
        response = client.get("/api/v1/observability/summary?task_id=task-a")
    assert response.status_code == 200
    data = response.json()
    assert data["measured"]["count"] == 1
    assert data["measured"]["median_total_ms"] == 10
    assert data["measured"]["prompt_tokens"] == 7
    assert data["estimates"] == {"cost_usd": None, "source": None, "status": "unavailable"}


def test_benchmarks_filters_coding_and_judge_reports(tmp_path, monkeypatch):
    coding = tmp_path / "LLMG-T12"
    judge = tmp_path / "LLMG-T15"
    coding.mkdir()
    judge.mkdir()
    (coding / "summary.json").write_text(json.dumps({
        "run_id": "run-1", "model": "coder:7b", "status": "inconclusive",
        "routes": {"direct": {"p50_latency_ms": 100, "functional_pass_rate": None,
                    "accepted_tasks_per_hour": 0, "tokens_total": 20}},
    }))
    (judge / "comparison.json").write_text(json.dumps({
        "dataset": "synthetic-v1", "status": "comparison_report_only",
        "splits": {"train": {"reviewers": {"judge:4b": {
            "latency_ms": 50, "accuracy_vs_synthetic_oracle": 1.0,
        }}}},
    }))
    monkeypatch.setattr(observability, "_BENCHMARK_DIR", tmp_path)
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))

    with TestClient(main.app) as client:
        coding_response = client.get("/api/v1/observability/benchmarks?role=coding")
        judge_response = client.get("/api/v1/observability/benchmarks?role=judge&model=judge%3A4b")
        empty_response = client.get("/api/v1/observability/benchmarks?role=judge&model=missing")
    assert coding_response.status_code == 200
    assert coding_response.json()["records"][0]["quality"] is None
    assert judge_response.json()["records"][0]["quality"] == pytest.approx(1.0)
    assert empty_response.json()["status"] == "empty"


def test_observability_skips_malformed_metric_rows_and_rejects_nonfinite_values(
    tmp_path, monkeypatch
):
    metrics = tmp_path / "ollama.jsonl"
    metrics.write_text(
        "\n".join(
            [
                "[]",
                "not-json",
                json.dumps(
                    {
                        "task_id": "task-safe",
                        "success": "false",
                        "total_ms": float("nan"),
                        "prompt_tokens": True,
                        "cost_usd": float("inf"),
                    }
                ),
                json.dumps(
                    {
                        "task_id": "task-ok",
                        "success": True,
                        "total_ms": 42,
                        "prompt_tokens": 8,
                        "cost_usd": 0.25,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    hardware = tmp_path / "hardware.json"
    hardware.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(observability, "_METRICS", metrics)
    monkeypatch.setattr(observability, "_HARDWARE", hardware)
    monkeypatch.setattr(main, "settings", replace(main.settings, auth_enabled=False))

    with TestClient(main.app) as client:
        response = client.get("/api/v1/observability/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["measured"]["count"] == 2
    assert data["measured"]["successful"] == 1
    assert data["measured"]["failed"] == 0
    assert data["measured"]["median_total_ms"] == 42
    assert data["measured"]["prompt_tokens"] == 8
    assert data["measured"]["cost_usd"] == pytest.approx(0.25)
    assert data["measured"]["hardware"] == {
        "status": "unavailable",
        "reason": "INVALID_PROBE_ARTIFACT",
    }
