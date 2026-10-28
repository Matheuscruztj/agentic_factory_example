#!/usr/bin/env python3
"""Combine required deterministic quality results into one agent-safe summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/quality-gates/src"))
from quality_gates.aggregate import DEFAULT_REQUIRED, aggregate_results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", nargs="*", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--required", action="append", default=[])
    args = parser.parse_args()
    required = tuple(args.required or DEFAULT_REQUIRED)
    paths = args.artifacts or [
        Path(f".runtime/quality/runs/{args.run_id}/{name.removeprefix('quality-')}.json")
        for name in required
    ]
    result = aggregate_results(paths, required=required, run_id=args.run_id)
    artifact = Path(".runtime/quality/aggregate.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(result, separators=(",", ":")))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
