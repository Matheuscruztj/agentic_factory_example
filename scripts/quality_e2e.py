#!/usr/bin/env python3
"""Browser acceptance against the disposable PostgreSQL-backed quality stack."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.quality_common import ROOT, QualityContext, print_result  # noqa: E402
from scripts.quality_stack import active_context, credentials, redact_artifacts  # noqa: E402


def main() -> int:
    try:
        ctx = active_context("quality-e2e")
    except (RuntimeError, OSError, ValueError) as exc:
        ctx = QualityContext("quality-e2e")
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
    for name, folder, arguments in [
        ("factory", "apps/factory-web", ["e2e/factory-live.spec.ts"]),
        ("registry", "apps/customer-registry/web", ["--config=e2e/playwright.config.ts"]),
    ]:
        report = ctx.artifacts / f"{name}-report.json"
        env = ctx.environment()
        env.update(
            FACTORY_OPERATOR_PASSWORD=credentials()["password"],
            FACTORY_TEST_EXTERNAL_SERVER="true",
            REGISTRY_TEST_EXTERNAL_SERVER="true",
            FACTORY_TEST_WEB_URL="http://127.0.0.1:18803",
            FACTORY_TEST_API_URL="http://127.0.0.1:18801",
            REGISTRY_TEST_WEB_URL="http://127.0.0.1:18804",
            FACTORY_TEST_OUTPUT_DIR=str(ctx.artifacts / "factory-results"),
            REGISTRY_TEST_OUTPUT_DIR=str(ctx.artifacts / "registry-results"),
            PLAYWRIGHT_JSON_OUTPUT_FILE=str(report),
        )
        step, _ = ctx.execute(
            name,
            ["pnpm", "exec", "playwright", "test", *arguments, "--reporter=json"],
            cwd=ROOT / folder,
            env=env,
        )
        try:
            stats = json.loads(report.read_text())["stats"]
            step["metrics"] = stats
            if stats["skipped"] or not (stats["expected"] + stats["unexpected"]):
                step.update(status="error", exit_code=2, error="E2E_SKIPPED_OR_EMPTY")
        except (OSError, KeyError, ValueError):
            step.update(status="error", exit_code=2, error="E2E_REPORT_MISSING_OR_INVALID")
        steps.append(step)
    redact_artifacts(ctx)
    return print_result(ctx.finish(steps))


if __name__ == "__main__":
    raise SystemExit(main())
