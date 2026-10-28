#!/usr/bin/env python3
"""Run local Python quality steps and emit one compact JSON result."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.quality_common import QualityContext  # noqa: E402

DEFAULT_MYPY_TARGETS = [
    "packages/task-engine/src/task_engine/execution.py",
    "packages/task-engine/src/task_engine/runs.py",
    "workers/src/factory_workers/runner.py",
    "packages/eval-engine/src/eval_engine/synthetic_judge.py",
    "apps/factory-api/src/factory_api/routers/agent_conversations.py",
    "apps/factory-api/src/factory_api/routers/approvals.py",
    "apps/factory-api/src/factory_api/routers/demands.py",
    "packages/task-engine/src/task_engine/models.py",
    "workers/src/factory_workers/github_cursor.py",
    "workers/src/factory_workers/github_poll.py",
    "workers/src/factory_workers/telegram_outbox.py",
    "workers/src/factory_workers/retries.py",
    "workers/src/factory_workers/retry_queue.py",
    "packages/agent-runtime/src/agent_runtime/review.py",
    "packages/agent-runtime/src/agent_runtime/sandbox.py",
    "packages/agent-runtime/src/agent_runtime/workflows/proposal_graph.py",
    "packages/integrations/src/integrations/github_publisher.py",
    "packages/quality-gates/src/quality_gates/schema.py",
    "packages/quality-gates/src/quality_gates/aggregate.py",
    "packages/eval-engine/src/eval_engine/schema.py",
    "packages/eval-engine/src/eval_engine/judge.py",
    "packages/eval-engine/src/eval_engine/experiments.py",
    "packages/eval-engine/src/eval_engine/reliability.py",
    "packages/eval-engine/src/eval_engine/meta_grader.py",
    "packages/observability/src/observability",
    "apps/factory-api/src/factory_api/routers/eval_feedback.py",
    "scripts/quality_python.py",
    "scripts/validate_checks.py",
    "workers/src/factory_workers/followups.py",
]


def summarize_output(name: str, output: str) -> dict[str, int]:
    if name == "pytest":
        return {
            key: int(value)
            for value, key in re.findall(r"(\d+) (passed|failed|skipped|error)", output)
        }
    if name == "mypy":
        match = re.search(r"Success: no issues found in (\d+) source files?", output)
        return {"source_files": int(match.group(1)), "issues": 0} if match else {}
    if name == "ruff":
        match = re.search(r"Found (\d+) errors?", output)
        return {"issues": int(match.group(1))} if match else {"issues": 0}
    return {}


def run_step(name: str, command: list[str], timeout: int, log_dir: Path) -> dict:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except FileNotFoundError:
        return {"name": name, "status": "error", "exit_code": 2, "error": "COMMAND_NOT_FOUND"}
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "error", "exit_code": 2, "error": "TIMEOUT"}
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{name}.log").write_text(
        result.stdout + result.stderr, encoding="utf-8", errors="replace"
    )
    code = result.returncode if result.returncode in (0, 1, 2) else 1
    return {
        "name": name,
        "status": {0: "pass", 1: "fail", 2: "error"}[code],
        "exit_code": code,
        "duration_seconds": round(time.monotonic() - started, 3),
        "artifact": f"{log_dir}/{name}.log",
        "metrics": summarize_output(name, result.stdout + result.stderr),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--mypy-target", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args()
    quality_context = QualityContext("quality-python")
    args.artifacts = args.artifacts or quality_context.artifacts
    if not 1 <= args.timeout <= 7200:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "check": "quality-python",
                    "status": "error",
                    "ok": 0,
                    "exit_code": 2,
                    "metrics": {},
                    "artifact": None,
                    "errors": ["INVALID_TIMEOUT"],
                }
            )
        )
        return 2
    targets = args.target or ["apps", "packages", "workers", "scripts", "tests"]
    mypy_targets = args.mypy_target or DEFAULT_MYPY_TARGETS
    mypy_path = [
        "packages/shared-contracts/src",
        "packages/task-engine/src",
        "packages/context-engine/src",
        "packages/integrations/src",
        "packages/agent-runtime/src",
        "packages/eval-engine/src",
        "packages/observability/src",
    ]
    env = os.environ.copy()
    existing_mypy_path = env.get("MYPYPATH", "")
    env["MYPYPATH"] = os.pathsep.join(
        [*mypy_path, *([existing_mypy_path] if existing_mypy_path else [])]
    )
    os.environ.update(env)
    steps = [
        run_step(
            "openapi-client",
            [sys.executable, "scripts/gen_client.py", "--check"],
            args.timeout,
            args.artifacts,
        ),
        run_step(
            "ruff",
            [sys.executable, "-m", "ruff", "check", *targets],
            args.timeout,
            args.artifacts,
        ),
        run_step(
            "mypy",
            [
                sys.executable,
                "-m",
                "mypy",
                "--follow-imports=silent",
                "--exclude",
                r"(^|/)alembic/env\.py$",
                *mypy_targets,
            ],
            args.timeout,
            args.artifacts,
        ),
        run_step(
            "pytest",
            [
                sys.executable,
                "-m",
                "coverage",
                "run",
                "--branch",
                "--source=apps,packages,workers,scripts",
                f"--data-file={args.artifacts / '.coverage'}",
                "-m",
                "pytest",
                "-q",
                *targets,
            ],
            args.timeout,
            args.artifacts,
        ),
        run_step(
            "coverage-xml",
            [
                sys.executable,
                "-m",
                "coverage",
                "xml",
                f"--data-file={args.artifacts / '.coverage'}",
                "-o",
                str(args.artifacts / "coverage.xml"),
            ],
            60,
            args.artifacts,
        ),
    ]
    if any(step["exit_code"] == 2 for step in steps):
        code = 2
    elif any(step["exit_code"] for step in steps):
        code = 1
    else:
        code = 0
    status = {0: "pass", 1: "fail", 2: "error"}[code]
    summary = {
        "schema": 1,
        "check": "quality-python",
        "status": status,
        "ok": int(code == 0),
        "exit_code": code,
        "steps": steps,
        "metrics": {
            "steps": len(steps),
            "passed": sum(step["status"] == "pass" for step in steps),
            "failed": sum(step["status"] == "fail" for step in steps),
            "errors": sum(step["status"] == "error" for step in steps),
        },
        "artifact": str(args.artifacts),
        "errors": [step.get("error", step["name"]) for step in steps if step["status"] != "pass"],
    }
    from scripts.quality_stack import redact_artifacts

    redact_artifacts(quality_context)
    summary = quality_context.finish(steps)
    summary_path = args.artifacts.parent / "python.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(summary, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
