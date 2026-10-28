"""Read-only summary of local metrics and hardware probes."""

from __future__ import annotations

import json
import math
import statistics
from collections.abc import Iterable
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/observability",
    tags=["observability"],
    dependencies=[Depends(require_operator)],
)
_ROOT = Path(__file__).resolve().parents[5]
_METRICS = _ROOT / ".runtime" / "observability" / "ollama.jsonl"
_HARDWARE = _ROOT / ".runtime" / "quality" / "hardware.json"
_BENCHMARK_DIR = _ROOT / ".runtime" / "artifacts" / "ai-acceptance"


@router.get("/summary")
def summary(task_id: str | None = Query(default=None, max_length=128)) -> dict:
    measurements = []
    if _METRICS.is_file():
        try:
            for line in _METRICS.read_text(encoding="utf-8").splitlines()[-2000:]:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if isinstance(item, dict) and (task_id is None or item.get("task_id") == task_id):
                    measurements.append(item)
        except (OSError, ValueError):
            measurements = []
    hardware = None
    if _HARDWARE.is_file():
        try:
            hardware = json.loads(_HARDWARE.read_text(encoding="utf-8"))
            if not isinstance(hardware, dict):
                hardware = {"status": "unavailable", "reason": "INVALID_PROBE_ARTIFACT"}
        except (OSError, ValueError):
            hardware = {"status": "unavailable", "reason": "INVALID_PROBE_ARTIFACT"}
    costs = [
        _number(item.get("cost_usd"))
        for item in measurements
        if _number(item.get("cost_usd")) is not None and _number(item.get("cost_usd")) >= 0
    ]
    return {
        "task_filter": task_id,
        "measured": {
            "count": len(measurements),
            "successful": sum(item.get("success") is True for item in measurements),
            "failed": sum(item.get("success") is False for item in measurements),
            "median_total_ms": _median(item.get("total_ms") for item in measurements),
            "median_queue_wait_ms": _median(item.get("queue_wait_ms") for item in measurements),
            "median_load_ms": _median(item.get("load_ms") for item in measurements),
            "median_generation_ms": _median(item.get("generation_ms") for item in measurements),
            "prompt_tokens": sum(_integer(item.get("prompt_tokens")) for item in measurements),
            "completion_tokens": sum(
                _integer(item.get("completion_tokens")) for item in measurements
            ),
            "cost_usd": sum(costs) if costs else None,
            "hardware": hardware,
        },
        "estimates": {"cost_usd": None, "source": None, "status": "unavailable"},
        "measurement_source": "local Ollama response timings and token counters",
    }


@router.get("/benchmarks")
def benchmarks(
    role: str | None = Query(default=None, pattern="^(coding|judge)$"),
    model: str | None = Query(default=None, max_length=128),
) -> dict:
    """Return a bounded, read-only view of persisted coding and Judge evaluations."""
    records: list[dict] = []
    for activity, filename, role_name in (
        ("LLMG-T12", "summary.json", "coding"),
        ("LLMG-T15", "comparison.json", "judge"),
    ):
        if role and role != role_name:
            continue
        path = _BENCHMARK_DIR / activity / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            return {"status": "error", "code": "INVALID_BENCHMARK_REPORT", "records": []}
        if role_name == "coding":
            for route, result in payload.get("routes", {}).items():
                record = {
                    "role": role_name,
                    "model": payload.get("model"),
                    "route": route,
                    "run_id": payload.get("run_id"),
                    "latency_ms": result.get("p50_latency_ms"),
                    "quality": result.get("functional_pass_rate"),
                    "accepted_tasks_per_hour": result.get("accepted_tasks_per_hour"),
                    "tokens": result.get("tokens_total"),
                    "status": payload.get("status"),
                    "trace": f"{activity}/{filename}",
                }
                if model is None or record["model"] == model:
                    records.append(record)
        else:
            for split, split_data in payload.get("splits", {}).items():
                for model_name, reviewer in split_data.get("reviewers", {}).items():
                    record = {
                        "role": role_name,
                        "model": model_name,
                        "route": split,
                        "run_id": payload.get("dataset"),
                        "latency_ms": reviewer.get("latency_ms"),
                        "quality": reviewer.get("accuracy_vs_synthetic_oracle"),
                        "accepted_tasks_per_hour": None,
                        "tokens": None,
                        "status": payload.get("status"),
                        "trace": f"{activity}/{filename}#{split}",
                    }
                    if model is None or record["model"] == model:
                        records.append(record)
    return {
        "status": "ready" if records else "empty",
        "filters": {"role": role, "model": model},
        "records": records[:200],
        "source": "bounded local evaluation reports",
    }


def _integer(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _median(values: Iterable[object]) -> float | None:
    observed = sorted(number for value in values if (number := _number(value)) is not None)
    if not observed:
        return None
    return statistics.median(observed)
