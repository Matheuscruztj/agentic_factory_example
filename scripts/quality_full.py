#!/usr/bin/env python3
"""Complete quality cycle: functional suites, SAST/DAST, local Sonar, then performance."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.quality_common import QualityContext, print_result, source_manifest  # noqa: E402
from scripts.validate_env import read_env  # noqa: E402


def parse_output(output: str) -> dict | None:
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    ctx = QualityContext("quality-full")
    env = ctx.environment()
    env["FACTORY_QUALITY_RUN_ID"] = ctx.run_id
    steps: list[dict] = []

    core_step, core_output = ctx.execute(
        "functional-and-security-gates",
        [sys.executable, "scripts/quality.py", "run", "--run-id", ctx.run_id],
        timeout=5400,
        env=env,
        json_output=True,
    )
    steps.append(core_step)
    core = parse_output(core_output)
    if core_step["status"] == "pass" and (core is None or core.get("run_id") != ctx.run_id):
        core_step.update(status="error", exit_code=2, error="QUALITY_CORE_RESULT_INVALID")
    elif core_step["status"] == "pass" and core.get("ok") != 1:
        core_step.update(status="fail", exit_code=1, error="QUALITY_CORE_REPORTED_FAILURE")

    sonar_env = dict(env)
    env_file = ROOT / ".env"
    if env_file.is_file():
        cfg = read_env(env_file)
        token = cfg.get("SONAR_TOKEN", "").strip()
        if token:
            sonar_env["SONAR_TOKEN"] = token
        sonar_env["SONAR_HOST_URL"] = cfg.get("SONAR_HOST_URL", "http://127.0.0.1:9001")
    sonar_step, sonar_output = ctx.execute(
        "sonar-local",
        [sys.executable, "scripts/quality_extended.py", "--profile", "sonar"],
        timeout=1800,
        env=sonar_env,
        json_output=True,
    )
    steps.append(sonar_step)
    sonar = parse_output(sonar_output)
    if sonar_step["status"] == "pass" and (
        sonar is None or sonar.get("check") != "quality-extended"
    ):
        sonar_step.update(status="error", exit_code=2, error="SONAR_RESULT_INVALID")
    elif sonar_step["status"] == "pass" and sonar.get("ok") != 1:
        sonar_step.update(status="fail", exit_code=1, error="SONAR_REPORTED_FAILURE")

    # This is deliberately last: no expensive load/performance check precedes feature gates.
    perf_step, perf_output = ctx.execute(
        "performance",
        [sys.executable, "scripts/quality_extended.py", "--profile", "perf"],
        timeout=900,
        env=env,
        json_output=True,
    )
    steps.append(perf_step)
    perf = parse_output(perf_output)
    if perf_step["status"] == "pass" and (
        perf is None or perf.get("check") != "quality-extended"
    ):
        perf_step.update(status="error", exit_code=2, error="PERFORMANCE_RESULT_INVALID")
    elif perf_step["status"] == "pass" and perf.get("ok") != 1:
        perf_step.update(status="fail", exit_code=1, error="PERFORMANCE_REPORTED_FAILURE")

    for token in (sonar_env.get("SONAR_TOKEN", ""),):
        if token:
            for path in ctx.artifacts.rglob("*"):
                if path.is_file() and not path.is_symlink() and path.suffix in {".log", ".json"}:
                    path.write_text(path.read_text(errors="replace").replace(token, "[REDACTED]"))

    if source_manifest()["source_sha256"] != ctx.manifest["source_sha256"]:
        steps.append({
            "name": "source-stability", "status": "error", "exit_code": 2,
            "error": "SOURCE_CHANGED_DURING_QUALITY_FULL",
        })
    result = ctx.finish(
        steps,
        profile="full",
        quality_run_id=ctx.run_id,
        sonar_run_id=sonar.get("run_id") if sonar else None,
        performance_run_id=perf.get("run_id") if perf else None,
        included=["frontend", "python", "e2e", "sast-sca-secrets", "dast", "sonar", "performance"],
        gate_summaries={
            "core": core,
            "sonar": sonar,
            "performance": perf,
        },
    )
    return print_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
