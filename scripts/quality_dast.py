#!/usr/bin/env python3
"""ZAP passive UI scans and active OpenAPI scans on isolated local services."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.quality_common import QualityContext, print_result  # noqa: E402
from scripts.quality_stack import active_context, compose, prepare_dast, redact_artifacts  # noqa: E402


def zap_result(step: dict, report: dict) -> dict:
    try:
        sites = report["site"]
        if step.get("error") or step.get("tool_exit_code") not in (0, 1, 2) or not sites:
            raise ValueError("ZAP_SCAN_INCOMPLETE")
        alerts = [a for site in sites for a in site["alerts"]]
        metrics = {
            name: sum(int(a["riskcode"]) == risk for a in alerts)
            for name, risk in [("critical", 4), ("high", 3), ("medium", 2), ("low", 1)]
        }
        metrics.update(alerts=len(alerts), sites=len(sites))
        block = bool(metrics["high"] or metrics["critical"])
        return {
            **step,
            "status": "fail" if block else "pass",
            "exit_code": int(block),
            "metrics": metrics,
        }
    except (KeyError, ValueError, TypeError):
        return {**step, "status": "error", "exit_code": 2, "error": "ZAP_REPORT_MISSING_OR_INVALID"}


def main() -> int:
    try:
        ctx = active_context("quality-dast")
    except (RuntimeError, OSError, ValueError) as exc:
        ctx = QualityContext("quality-dast")
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
    command, env = compose(ctx)
    try:
        coverage = prepare_dast(ctx)
    except Exception as exc:
        return print_result(
            ctx.finish(
                [
                    {
                        "name": "authenticated-target-smoke",
                        "status": "error",
                        "exit_code": 2,
                        "error": type(exc).__name__,
                    }
                ]
            )
        )
    steps = []
    for name, kind in [
        ("factory-web", "baseline"),
        ("registry-web", "baseline"),
        ("factory-api", "api-scan"),
        ("registry-api", "api-scan"),
    ]:
        report_path = ctx.artifacts / f"{name}.json"
        report_path.unlink(missing_ok=True)
        target = (
            f"http://{name}:8080/"
            if kind == "baseline"
            else (f"/zap/wrk/{name.removesuffix('-api')}-openapi.json")
        )
        args = ["-t", target, "-I", "-T", "3", "-J", f"{name}.json", "-r", f"{name}.html"]
        if kind == "baseline":
            args += ["-m", "1"]
        else:
            args += [
                "-f",
                "openapi",
                "--hook",
                "/opt/quality/zap_hooks.py",
                "-z",
                "-config scanner.threadPerHost=2 -config ascan.maxScanDurationInMins=3",
            ]
        step, output = ctx.execute(
            name,
            command
            + ["--profile", "dast", "run", "--rm", "--entrypoint", f"zap-{kind}.py", "zap", *args],
            env=env,
            timeout=900,
        )
        try:
            report = json.loads(report_path.read_text())
        except (OSError, ValueError):
            report = {}
        step = zap_result(step, report)
        urls = re.search(r"Total of (\d+) URLs", output)
        if not urls or int(urls.group(1)) <= 0:
            step.update(status="error", exit_code=2, error="ZAP_NO_URLS_SCANNED")
        else:
            step.setdefault("metrics", {})["urls"] = int(urls.group(1))
        steps.append(step)
    redact_artifacts(ctx)
    return print_result(
        ctx.finish(
            steps,
            coverage=coverage,
            blocking_policy="ZAP high/critical; medium/low remain reported",
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
