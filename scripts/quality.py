#!/usr/bin/env python3
"""Run all mandatory gates against one source snapshot and isolated Docker targets."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/quality-gates/src"))
from quality_gates.aggregate import DEFAULT_REQUIRED, aggregate_results  # noqa: E402

from scripts.quality_common import QUALITY, QualityContext, print_result, source_manifest  # noqa: E402
from scripts.quality_stack import compose, credentials, start  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=["run", "up", "down"], default="run")
    parser.add_argument("--perf", action="store_true", help="Also run the local Locust smoke")
    parser.add_argument("--run-id", help="Join an existing quality run (used by quality-full)")
    args = parser.parse_args()
    QUALITY.mkdir(parents=True, exist_ok=True)
    with (QUALITY / "runner.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                json.dumps(
                    {
                        "schema": 1,
                        "check": "quality-run",
                        "ok": 0,
                        "status": "error",
                        "exit_code": 2,
                        "metrics": {},
                        "artifact": None,
                        "errors": ["QUALITY_RUN_ALREADY_ACTIVE"],
                    }
                )
            )
            return 2
        if args.run_id:
            os.environ["FACTORY_QUALITY_RUN_ID"] = args.run_id
        else:
            os.environ.pop("FACTORY_QUALITY_RUN_ID", None)
        ctx = QualityContext("quality-run", run_id=args.run_id)
        os.environ["FACTORY_QUALITY_RUN_ID"] = ctx.run_id
        if args.action == "down":
            command, env = compose(ctx)
            step, _ = ctx.execute(
                "stop-test-stack", command + ["down", "--remove-orphans"], env=env
            )
            return print_result(ctx.finish([step]))
        steps = []
        gates = ["frontend"] if args.action == "up" else ["frontend", "security"]
        for gate in gates:
            step, _ = ctx.execute(
                gate, [sys.executable, f"scripts/quality_{gate}.py"], timeout=1200
            )
            steps.append(step)
        frontend = ctx.run_dir / "frontend.json"
        ready = frontend.exists() and json.loads(frontend.read_text())["status"] == "pass"
        if ready:
            stack = start(ctx)
            steps.extend(stack)
            ready = all(s["status"] == "pass" for s in stack)
        if ready and args.action == "run":
            for gate in ["python", "e2e", "dast", *(["extended"] if args.perf else [])]:
                env = ctx.environment()
                if gate == "python":
                    password = credentials()["QUALITY_DB_PASSWORD"]
                    env["DATABASE_URL"] = (
                        f"postgresql+psycopg://quality:{password}@127.0.0.1:18832/factory"
                    )
                command = [sys.executable, f"scripts/quality_{gate}.py"]
                if gate == "extended":
                    command += ["--profile", "perf"]
                step, _ = ctx.execute(gate, command, timeout=3600, env=env)
                steps.append(step)
        if source_manifest()["source_sha256"] != ctx.manifest["source_sha256"]:
            steps.append(
                {
                    "name": "source-stability",
                    "status": "error",
                    "exit_code": 2,
                    "error": "SOURCE_CHANGED_DURING_QUALITY_RUN",
                }
            )
        if args.action == "up":
            return print_result(
                ctx.finish(
                    steps,
                    services={
                        "factory": "http://127.0.0.1:18803",
                        "registry": "http://127.0.0.1:18804",
                    },
                )
            )
        paths = [ctx.run_dir / f"{name.removeprefix('quality-')}.json" for name in DEFAULT_REQUIRED]
        result = aggregate_results(paths, run_id=ctx.run_id)
        orchestration_failures = [step for step in steps if step["status"] != "pass"]
        if orchestration_failures:
            has_error = any(step["status"] == "error" for step in orchestration_failures)
            result.update(
                status="error" if has_error else "fail",
                ok=0,
                exit_code=2 if has_error else 1,
                errors=[step.get("error", step["name"]) for step in orchestration_failures],
            )
            result["metrics"]["errors"] += sum(
                step["status"] == "error" for step in orchestration_failures
            )
            result["metrics"]["failed"] += sum(
                step["status"] == "fail" for step in orchestration_failures
            )
        result.update(
            git_sha=ctx.manifest["git_sha"],
            source_sha256=ctx.manifest["source_sha256"],
            run_artifact=str(ctx.run_dir),
            orchestration_steps=steps,
        )
        encoded = json.dumps(result, separators=(",", ":")) + "\n"
        (ctx.run_dir / "aggregate.json").write_text(encoded)
        (QUALITY / "aggregate.json").write_text(encoded)
        return print_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
