#!/usr/bin/env python3
"""Paired local Ollama vs LiteLLM latency probe with explicit model identity."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import uuid
from pathlib import Path

import httpx

MAX_OUTPUT_TOKENS = 32
TEMPERATURE = 0


def _key_from_local_env(name: str) -> str:
    key = os.getenv(name, "")
    path = Path(".env")
    if key or not path.is_file() or path.is_symlink():
        return key
    for raw in path.read_text(encoding="utf-8").splitlines():
        variable, separator, value = raw.partition("=")
        if separator and variable.strip() == name:
            return value.strip().strip("\"'")
    return ""


def _call(
    client: httpx.Client,
    route: str,
    model: str,
    prompt: str,
    key: str,
    direct_url: str,
    proxy_url: str,
) -> dict:
    started = time.perf_counter()
    if route == "direct":
        response = client.post(
            direct_url.rstrip("/") + "/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": TEMPERATURE, "num_predict": MAX_OUTPUT_TOKENS},
            },
        )
    else:
        response = client.post(
            proxy_url.rstrip("/") + "/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "chat",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "reasoning_effort": "minimal",
            },
        )
    response.raise_for_status()
    payload = response.json()
    if route == "direct":
        content = payload.get("message", {}).get("content", "")
        prompt_tokens, completion_tokens = (
            payload.get("prompt_eval_count"),
            payload.get("eval_count"),
        )
    else:
        choice = (payload.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        usage = payload.get("usage") or {}
        prompt_tokens, completion_tokens = (
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"EMPTY_RESPONSE:{route}")
    return {
        "route": route,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "response_chars": len(content),
        "error_class": None,
    }


def run(
    *,
    repeats: int,
    model: str,
    key: str,
    output: Path,
    direct_url: str = "http://127.0.0.1:11434",
    proxy_url: str = "http://127.0.0.1:4000",
) -> dict:
    if not 1 <= repeats <= 20:
        raise ValueError("REPEATS_OUT_OF_RANGE")
    prompt = "Responda apenas OK. Código de medição sintético " + uuid.uuid4().hex[:8]
    samples = []
    with httpx.Client(timeout=90, trust_env=False) as client:
        # Warm both routes, then alternate the order as D-P-P-D to reduce order bias.
        for route in ("direct", "proxy"):
            samples.append(
                {
                    **_call(client, route, model, prompt, key, direct_url, proxy_url),
                    "warmup": True,
                    "pair": 0,
                }
            )
        for pair in range(1, repeats + 1):
            order = (
                ("direct", "proxy", "proxy", "direct")
                if pair % 2
                else ("proxy", "direct", "direct", "proxy")
            )
            for route in order:
                samples.append(
                    {
                        **_call(client, route, model, prompt, key, direct_url, proxy_url),
                        "warmup": False,
                        "pair": pair,
                    }
                )
    measured = [item for item in samples if not item["warmup"]]
    by_route = {
        route: [x["latency_ms"] for x in measured if x["route"] == route]
        for route in ("direct", "proxy")
    }
    paired_deltas = []
    for pair in range(1, repeats + 1):
        values = {
            route: [x["latency_ms"] for x in measured if x["pair"] == pair and x["route"] == route]
            for route in by_route
        }
        paired_deltas.append(
            statistics.median(values["proxy"]) - statistics.median(values["direct"])
        )
    enough = repeats >= 5
    report = {
        "schema": 1,
        "run_id": uuid.uuid4().hex,
        "model": model,
        "route_alias": "chat",
        "sampling": {
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "reasoning": "disabled/minimal on direct/proxy respectively",
            "prompt_sha256": __import__("hashlib").sha256(prompt.encode()).hexdigest(),
        },
        "warmup_calls": 2,
        "pairing": "alternating ABBA/BAAB",
        "pairs": repeats,
        "samples_per_route": {route: len(values) for route, values in by_route.items()},
        "metrics": {
            route: {
                "p50_ms": round(statistics.median(values), 3),
                "p95_ms": round(sorted(values)[max(0, int(len(values) * 0.95) - 1)], 3),
                "mean_ms": round(statistics.mean(values), 3),
            }
            for route, values in by_route.items()
        },
        "paired_proxy_minus_direct_ms": [round(value, 3) for value in paired_deltas],
        "status": "complete" if enough else "inconclusive_insufficient_pairs",
        "conclusion": None,
        "samples": samples,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--direct-url", default="http://127.0.0.1:11434")
    parser.add_argument("--proxy-url", default="http://127.0.0.1:4400")
    parser.add_argument("--key-env", default="LITELLM_MASTER_KEY")
    parser.add_argument(
        "--output", type=Path, default=Path(".runtime/benchmarks/gateway/latest.json")
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({"check": "gateway-compare", "ok": 1, "inference": False}))
        return 0
    key = _key_from_local_env(args.key_env)
    if not key:
        print(json.dumps({"check": "gateway-compare", "ok": 0, "error": "KEY_MISSING"}))
        return 2
    try:
        report = run(
            repeats=args.repeats,
            model=args.model,
            key=key,
            output=args.output,
            direct_url=args.direct_url,
            proxy_url=args.proxy_url,
        )
    except (httpx.HTTPError, ValueError) as exc:
        print(json.dumps({"check": "gateway-compare", "ok": 0, "error": type(exc).__name__}))
        return 2 if isinstance(exc, httpx.HTTPError) else 1
    print(
        json.dumps(
            {
                "check": "gateway-compare",
                "ok": 1,
                "run_id": report["run_id"],
                "pairs": report["pairs"],
                "status": report["status"],
                "report": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
