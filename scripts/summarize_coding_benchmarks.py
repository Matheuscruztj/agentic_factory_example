#!/usr/bin/env python3
"""Summarize coding trials without treating model responses as accepted patches."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def summarize(paths: list[Path]) -> dict:
    rows = [
        json.loads(line) for path in paths for line in path.read_text().splitlines() if line.strip()
    ]
    if not rows:
        raise ValueError("BENCHMARK_TRIALS_REQUIRED")
    routes = sorted({row["route"] for row in rows})
    result = {}
    for route in routes:
        items = [row for row in rows if row["route"] == route]
        accepted = [row for row in items if row.get("accepted") is True]
        latencies = [
            row["latency_ms"] for row in items if isinstance(row.get("latency_ms"), (int, float))
        ]
        token_total = sum(
            (row.get("prompt_tokens") or 0) + (row.get("completion_tokens") or 0) for row in items
        )
        elapsed_hours = sum((row.get("latency_ms") or 0) for row in items) / 3_600_000
        accepted_hours = elapsed_hours if elapsed_hours > 0 else None
        by_size = {}
        for size in ("small", "long", "unclassified"):
            stratum = [row for row in items if row.get("task_size", "unclassified") == size]
            size_accepted = [row for row in stratum if row.get("accepted") is True]
            by_size[size] = {
                "trials": len(stratum),
                "accepted": len(size_accepted),
                "quality_status": "not_evaluated"
                if not stratum or all("accepted" not in row for row in stratum)
                else "measured",
            }
        result[route] = {
            "trials": len(items),
            "accepted_tasks": len(accepted),
            "accepted_tasks_per_hour": round(len(accepted) / accepted_hours, 4)
            if accepted_hours and accepted
            else 0.0,
            "tokens_total": token_total,
            "tokens_per_accepted_task": round(token_total / len(accepted), 2) if accepted else None,
            "functional_pass_rate": round(len(accepted) / len(items), 4)
            if any("accepted" in row for row in items)
            else None,
            "p50_latency_ms": round(statistics.median(latencies), 3) if latencies else None,
            "task_size_strata": by_size,
        }
    accepted_count = max(
        (
            sum(row["route"] == route and row.get("accepted") is True for row in rows)
            for route in routes
        ),
        default=0,
    )
    report = {
        "schema": 1,
        "routes": result,
        "winner": None,
        "status": "inconclusive_no_accepted_patch_trials"
        if accepted_count == 0
        else "inconclusive_insufficient_accepted_trials"
        if accepted_count < 5
        else "metrics_available",
        "conclusion": None,
        "method": (
            "Accepted means deterministic coding gates passed for an applied patch; "
            "response-only trials remain unaccepted."
        ),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=Path, action="append", default=[])
    parser.add_argument(
        "--output", type=Path, default=Path(".runtime/benchmarks/coding/summary.json")
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({"check": "coding-benchmark-summary", "ok": 1, "inference": False}))
        return 0
    if not args.trials:
        print(
            json.dumps({"check": "coding-benchmark-summary", "ok": 0, "error": "TRIALS_REQUIRED"})
        )
        return 1
    try:
        report = summarize(args.trials)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps({"check": "coding-benchmark-summary", "ok": 0, "error": type(exc).__name__})
        )
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    markdown = [
        "# Coding benchmark efficiency",
        "",
        f"Status: `{report['status']}`. No winner declared.",
        "",
        "| Route | Trials | Accepted tasks/h | Tokens/accepted task | p50 latency ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for route, metrics in report["routes"].items():
        markdown.append(
            f"| {route} | {metrics['trials']} | {metrics['accepted_tasks_per_hour']} | "
            f"{metrics['tokens_per_accepted_task']} | {metrics['p50_latency_ms']} |"
        )
    args.output.with_suffix(".md").write_text("\n".join(markdown) + "\n")
    print(
        json.dumps(
            {
                "check": "coding-benchmark-summary",
                "ok": 1,
                "status": report["status"],
                "report": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
