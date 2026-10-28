#!/usr/bin/env python3
"""Explicit optional performance/Sonar checks; DAST uses the mandatory runner."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.quality_common import QualityContext, print_result  # noqa: E402
from scripts.quality_stack import active_context, redact_artifacts  # noqa: E402

SONAR_LOCAL_GATE = "A-Fabric Local"
SONAR_NEW_COVERAGE_MINIMUM = "78"


def configure_sonar_gate(host: str) -> None:
    """Copy Sonar's standard local gate and keep its thresholds reproducible."""
    password_path = Path(__file__).resolve().parents[1] / ".runtime/sonar-admin-password.txt"
    if not password_path.is_file():
        raise RuntimeError("SONAR_LOCAL_ADMIN_CREDENTIAL_MISSING")
    with httpx.Client(
        base_url=host.rstrip("/"),
        auth=("admin", password_path.read_text(encoding="utf-8").strip()),
        timeout=20,
    ) as client:
        gates = client.get("/api/qualitygates/list").raise_for_status()
        names = {gate["name"] for gate in gates.json().get("qualitygates", [])}
        if SONAR_LOCAL_GATE not in names:
            client.post(
                "/api/qualitygates/copy",
                data={"sourceName": "Sonar way", "name": SONAR_LOCAL_GATE},
            ).raise_for_status()
        gate = client.get(
            "/api/qualitygates/show", params={"name": SONAR_LOCAL_GATE}
        ).raise_for_status().json()
        conditions = gate.get("conditions", [])
        violations = next(
            (item for item in conditions if item.get("metric") == "new_violations"), None
        )
        coverage = next(
            (item for item in conditions if item.get("metric") == "new_coverage"), None
        )
        if violations is None or coverage is None:
            raise RuntimeError("SONAR_LOCAL_GATE_STANDARD_CONDITIONS_MISSING")
        if coverage.get("error") != SONAR_NEW_COVERAGE_MINIMUM:
            client.post(
                "/api/qualitygates/update_condition",
                data={
                    "id": coverage["id"],
                    "metric": "new_coverage",
                    "op": "LT",
                    "error": SONAR_NEW_COVERAGE_MINIMUM,
                },
            ).raise_for_status()
        client.post(
            "/api/qualitygates/select",
            data={"projectKey": "agentic-factory-local", "gateName": SONAR_LOCAL_GATE},
        ).raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["perf", "dast", "sonar", "all"], required=True)
    args = parser.parse_args()
    if args.profile == "dast":
        from scripts.quality_dast import main as dast

        return dast()
    try:
        ctx = (
            active_context("quality-extended")
            if args.profile in {"perf", "all"}
            else QualityContext("quality-extended")
        )
    except (RuntimeError, OSError, ValueError) as exc:
        ctx = QualityContext("quality-extended")
        return print_result(
            ctx.finish(
                [
                    {
                        "name": "target-provenance",
                        "status": "error",
                        "exit_code": 2,
                        "error": str(exc),
                    }
                ]
            )
        )
    steps = []
    if args.profile in {"perf", "all"}:
        step, _ = ctx.execute(
            "locust",
            [
                sys.executable,
                "-m",
                "locust",
                "-f",
                "scripts/quality_locustfile.py",
                "--headless",
                "--host",
                "http://127.0.0.1:18801",
                "--users",
                "2",
                "--spawn-rate",
                "1",
                "--run-time",
                "10s",
                "--exit-code-on-error",
                "1",
                "--csv",
                str(ctx.artifacts / "locust"),
            ],
            timeout=120,
        )
        try:
            with (ctx.artifacts / "locust_stats.csv").open() as stream:
                row = next(r for r in csv.DictReader(stream) if r["Name"] == "Aggregated")
            requests, failures = int(row["Request Count"]), int(row["Failure Count"])
            step["metrics"] = {"requests": requests, "failures": failures}
            if requests <= 0:
                raise ValueError("NO_REQUESTS")
            if failures:
                step.update(status="fail", exit_code=1)
        except (OSError, ValueError, KeyError, StopIteration):
            step.update(status="error", exit_code=2, error="LOCUST_METRICS_MISSING_OR_EMPTY")
        steps.append(step)
    if args.profile == "all":
        step, _ = ctx.execute("dast", [sys.executable, "scripts/quality_dast.py"], timeout=3600)
        steps.append(step)
    if args.profile in {"sonar", "all"}:
        if not os.getenv("SONAR_TOKEN"):
            steps.append(
                {
                    "name": "sonar",
                    "status": "error",
                    "exit_code": 2,
                    "error": "SONAR_TOKEN_REQUIRED_FOR_SELECTED_PROFILE",
                }
            )
        else:
            if not os.getenv("SONAR_HOST_URL", "http://127.0.0.1:9001").startswith(
                "http://127.0.0.1:9001"
            ):
                steps.append(
                    {
                        "name": "sonar-host",
                        "status": "error",
                        "exit_code": 2,
                        "error": "SONAR_PROFILE_USES_LOCAL_DOCKER_INSTANCE_127_0_0_1_9001",
                    }
                )
                redact_artifacts(ctx)
                return print_result(ctx.finish(steps))
            try:
                configure_sonar_gate("http://127.0.0.1:9001")
                steps.append(
                    {
                        "name": "sonar-local-gate",
                        "status": "pass",
                        "exit_code": 0,
                        "metrics": {
                            "gate": SONAR_LOCAL_GATE,
                            "new_python_coverage_minimum": SONAR_NEW_COVERAGE_MINIMUM,
                            "new_violations": 0,
                        },
                    }
                )
            except (httpx.HTTPError, RuntimeError, OSError) as exc:
                steps.append(
                    {
                        "name": "sonar-local-gate",
                        "status": "error",
                        "exit_code": 2,
                        "error": (
                            str(exc)
                            if isinstance(exc, RuntimeError)
                            else "SONAR_LOCAL_GATE_CONFIGURATION_FAILED"
                        ),
                    }
                )
                redact_artifacts(ctx)
                return print_result(ctx.finish(steps))
            command = [
                "docker",
                "compose",
                "-p",
                "a-fabric-sonar",
                "-f",
                str(Path(__file__).resolve().parents[1] / "infra/compose/sonar-local.yml"),
                "--profile",
                "scanner",
            ]
            env = ctx.environment()
            env["QUALITY_SOURCE_PATH"] = str(ctx.snapshot())
            step, _ = ctx.execute(
                "sonar-start",
                [
                    "docker",
                    "compose",
                    "-p",
                    "a-fabric-sonar",
                    "-f",
                    str(Path(__file__).resolve().parents[1] / "infra/compose/sonar-local.yml"),
                    "up",
                    "-d",
                    "--wait",
                    "sonarqube",
                ],
                env=env,
                timeout=900,
            )
            steps.append(step)
            if step["status"] == "pass":
                step, scanner_output = ctx.execute(
                    "sonar-quality-gate",
                    command
                    + [
                        "run",
                        "--rm",
                        "sonar-scanner",
                        "-Dsonar.projectBaseDir=/usr/src",
                        "-Dsonar.qualitygate.wait=true",
                        "-Dsonar.qualitygate.timeout=300",
                    ],
                    env=env,
                    timeout=900,
                )
                if "QUALITY GATE STATUS: FAILED" in scanner_output:
                    step.update(status="fail", exit_code=1, error="SONAR_QUALITY_GATE_FAILED")
                steps.append(step)
            else:
                steps.append(
                    {
                        "name": "sonar-ready",
                        "status": "error",
                        "exit_code": 2,
                        "error": "SONARQUBE_HEALTHCHECK_FAILED",
                    }
                )
    redact_artifacts(ctx)
    return print_result(ctx.finish(steps))


if __name__ == "__main__":
    raise SystemExit(main())
