#!/usr/bin/env python3
"""Run bounded coding quality tools and emit compact 0/1/2 JSON status."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/quality-gates/src"))
from quality_gates.tool_adapter import run_quality_tool  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--run-id", default=uuid.uuid4().hex[:16])
    parser.add_argument("--semgrep", action="store_true", help="include optional Semgrep scan")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    targets = args.target or ["packages/quality-gates/src/quality_gates/tool_adapter.py"]
    if any(Path(target).is_absolute() or ".." in Path(target).parts for target in targets):
        print(
            json.dumps(
                {"check": "llm-quality", "ok": 0, "exit_code": 2, "error": "TARGET_PATH_INVALID"},
                separators=(",", ":"),
            )
        )
        return 2
    commands = [
        ("ruff", ["uv", "run", "ruff", "check", *targets], False),
        ("pytest", ["uv", "run", "pytest", "tests/unit/test_quality_tool_adapter.py", "-q"], False),
        ("mypy", ["uv", "run", "mypy", *targets], False),
    ]
    if args.semgrep:
        commands.append(("semgrep", ["semgrep", "scan", "--config", "p/python", *targets], True))
    if args.dry_run:
        print(
            json.dumps(
                {
                    "check": "llm-quality",
                    "ok": 1,
                    "exit_code": 0,
                    "tools": [name for name, _, _ in commands],
                    "inference": False,
                },
                separators=(",", ":"),
            )
        )
        return 0
    artifact_dir = ROOT / ".runtime/quality/llm-benchmark" / args.run_id
    results = [
        run_quality_tool(command, tool=name, artifact_dir=artifact_dir, optional=optional).to_dict()
        for name, command, optional in commands
    ]
    exit_code = (
        2
        if any(item["exit_code"] == 2 for item in results)
        else (1 if any(item["exit_code"] == 1 for item in results) else 0)
    )
    report = {
        "schema": 1,
        "check": "llm-quality",
        "ok": int(exit_code == 0),
        "exit_code": exit_code,
        "run_id": args.run_id,
        "results": results,
        "classification": "infrastructure"
        if exit_code == 2
        else "code"
        if exit_code == 1
        else "pass",
    }
    report_path = artifact_dir / "result.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "check": report["check"],
                "ok": report["ok"],
                "exit_code": exit_code,
                "run_id": args.run_id,
                "classification": report["classification"],
                "artifact": str(report_path.relative_to(ROOT)),
            },
            separators=(",", ":"),
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
