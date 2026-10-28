#!/usr/bin/env python3
"""Run a bounded public coding fixture through direct Ollama, LiteLLM, or both."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def _local_key() -> str:
    key = os.getenv("LITELLM_MASTER_KEY", "")
    path = ROOT / ".env"
    if key or not path.is_file() or path.is_symlink():
        return key
    for raw in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = raw.partition("=")
        if separator and name.strip() == "LITELLM_MASTER_KEY":
            return value.strip().strip("\"'")
    return ""


def public_fixture(path: Path) -> tuple[dict, str]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    prompt_lines = [fixture["description"], "Requirements:"]
    prompt_lines.extend(f"- {x}" for x in fixture["visible_requirements"])
    prompt_lines.extend(["Allowed paths:", *[f"- {x}" for x in fixture["allowed_paths"]]])
    prompt_lines.append(
        "Return a concise proposed patch; do not request secrets or use network access."
    )
    prompt = "\n".join(prompt_lines)
    return fixture, prompt


def _models(base_url: str, model: str) -> str | None:
    try:
        response = httpx.get(base_url.rstrip("/") + "/api/tags", timeout=5, trust_env=False)
        response.raise_for_status()
        items = response.json().get("models", [])
        return next((item.get("digest") for item in items if item.get("name") == model), None)
    except (httpx.HTTPError, ValueError):
        return None


def _vram(base_url: str, model: str) -> int | None:
    try:
        response = httpx.get(base_url.rstrip("/") + "/api/ps", timeout=3, trust_env=False)
        response.raise_for_status()
        items = response.json().get("models", [])
        return next((item.get("size_vram") for item in items if item.get("name") == model), None)
    except (httpx.HTTPError, ValueError):
        return None


def _request(
    route: str,
    prompt: str,
    *,
    model: str,
    key: str,
    direct_url: str,
    proxy_url: str,
    num_ctx: int,
    max_tokens: int,
    timeout: int,
) -> dict:
    started = time.perf_counter()
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        if route == "direct":
            response = client.post(
                direct_url.rstrip("/") + "/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": max_tokens},
                },
            )
            response.raise_for_status()
            result = response.json()
            message = result.get("message") or {}
            content = message.get("content") or ""
            prompt_tokens, completion_tokens = (
                result.get("prompt_eval_count"),
                result.get("eval_count"),
            )
        else:
            response = client.post(
                proxy_url.rstrip("/") + "/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": "coding",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": max_tokens,
                    "extra_body": {"options": {"num_ctx": num_ctx}},
                },
            )
            response.raise_for_status()
            result = response.json()
            content = ((result.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            usage = result.get("usage") or {}
            prompt_tokens, completion_tokens = (
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("EMPTY_MODEL_RESPONSE")
    return {
        "route": route,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "response_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "response_chars": len(content),
        "error_class": None,
    }


def run(args: argparse.Namespace, *, key: str) -> dict:
    if args.repeats < 1 or args.repeats > 10 or args.num_ctx < 256 or args.max_tokens < 1:
        raise ValueError("BUDGET_INVALID")
    fixture_path = ROOT / args.fixture
    fixture, prompt = public_fixture(fixture_path)
    routes = ("direct", "proxy") if args.route == "compare" else (args.route,)
    run_id = uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    models = {route: _models(args.direct_url, args.model) for route in routes}
    trials = []
    for route in routes:
        for repetition in range(1, args.repeats + 1):
            started_at = datetime.now(UTC).isoformat()
            vram_before = _vram(args.direct_url, args.model)
            try:
                sample = _request(
                    route,
                    prompt,
                    model=args.model,
                    key=key,
                    direct_url=args.direct_url,
                    proxy_url=args.proxy_url,
                    num_ctx=args.num_ctx,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                )
                outcome = "response_received"
            except httpx.TimeoutException:
                sample = {
                    "route": route,
                    "latency_ms": None,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "error_class": "timeout",
                }
                outcome = "infrastructure_error"
            except httpx.HTTPError as exc:
                sample = {
                    "route": route,
                    "latency_ms": None,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "error_class": "gateway_error" if route == "proxy" else "model_failure",
                    "error_type": type(exc).__name__,
                }
                outcome = "infrastructure_error"
            vram_after = _vram(args.direct_url, args.model)
            trials.append(
                {
                    "run_id": run_id,
                    "task_id": fixture["id"],
                    "trace_id": trace_id,
                    "model": args.model,
                    "model_digest": models[route],
                    "route": route,
                    "prompt_version": "fixture-visible-v1",
                    "dataset_version": "customer-registry-coding-v1",
                    "repetition": repetition,
                    "budget": {"num_ctx": args.num_ctx, "max_tokens": args.max_tokens},
                    "started_at": started_at,
                    "finished_at": datetime.now(UTC).isoformat(),
                    "outcome": outcome,
                    "vram_before_bytes": vram_before,
                    "vram_after_bytes": vram_after,
                    **sample,
                }
            )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_path = output.with_suffix(".jsonl")
    raw_path.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in trials))
    good = [item for item in trials if item.get("latency_ms") is not None]
    summary = {
        "schema": 1,
        "run_id": run_id,
        "dataset": "customer-registry-coding-v1",
        "fixture_id": fixture["id"],
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "model": args.model,
        "routes": routes,
        "repeats": args.repeats,
        "num_ctx": args.num_ctx,
        "max_tokens": args.max_tokens,
        "samples": len(good),
        "failures": len(trials) - len(good),
        "tokens": {
            route: sum(
                (x.get("prompt_tokens") or 0) + (x.get("completion_tokens") or 0)
                for x in good
                if x["route"] == route
            )
            for route in routes
        },
        "accepted": 0,
        "accepted_tasks_per_hour": 0.0,
        "quality_status": "not_evaluated_no_patch_applied",
        "latency_p50_ms": statistics.median([x["latency_ms"] for x in good]) if good else None,
        "vram_peak_bytes": max(
            (x["vram_after_bytes"] for x in trials if isinstance(x.get("vram_after_bytes"), int)),
            default=None,
        ),
        "raw_jsonl": str(raw_path),
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--route", choices=("direct", "proxy", "compare"), default="compare")
    parser.add_argument("--fixture", default="evals/fixtures/bug-cpf/case.json")
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--direct-url", default="http://127.0.0.1:11434")
    parser.add_argument("--proxy-url", default="http://127.0.0.1:4400")
    parser.add_argument("--output", default=".runtime/benchmarks/coding/latest.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "check": "coding-benchmark",
                    "ok": 1,
                    "inference": False,
                    "fixture": args.fixture,
                    "route": args.route,
                }
            )
        )
        return 0
    key = _local_key()
    if args.route in {"proxy", "compare"} and not key:
        print(json.dumps({"check": "coding-benchmark", "ok": 0, "error": "KEY_MISSING"}))
        return 2
    try:
        result = run(args, key=key)
    except (OSError, ValueError, httpx.HTTPError) as exc:
        print(json.dumps({"check": "coding-benchmark", "ok": 0, "error": type(exc).__name__}))
        return 2 if isinstance(exc, httpx.HTTPError) else 1
    print(
        json.dumps(
            {
                "check": "coding-benchmark",
                "ok": int(result["samples"] > 0),
                "run_id": result["run_id"],
                "samples": result["samples"],
                "failures": result["failures"],
                "report": args.output,
                "raw": result["raw_jsonl"],
            }
        )
    )
    return 0 if result["samples"] == len(result["routes"]) * result["repeats"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
