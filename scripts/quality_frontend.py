#!/usr/bin/env python3
"""Verify both frontends and retain immutable built assets for the quality stack."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.quality_common import ROOT, QualityContext, print_result  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.parse_args()
    ctx = QualityContext("quality-frontend")
    steps = []
    applications = [
        ("factory", ROOT / "apps/factory-web"),
        ("registry", ROOT / "apps/customer-registry/web"),
    ]
    for name, folder in applications:
        env = ctx.environment()
        env["VITE_FACTORY_API_URL"] = "http://127.0.0.1:18801"
        env["VITE_REGISTRY_API_URL"] = "http://127.0.0.1:18810"
        for label, command in [
            ("vitest", ["pnpm", "test"]),
            ("eslint", ["pnpm", "lint"]),
            ("typecheck", ["pnpm", "typecheck"]),
            ("build", ["pnpm", "build"]),
        ]:
            if label == "vitest":
                command = [
                    *command,
                    "--coverage.enabled",
                    "--coverage.reporter=lcov",
                    f"--coverage.reportsDirectory={ctx.artifacts / f'{name}-coverage'}",
                ]
            step_env = dict(env)
            if label != "build":
                step_env.pop("VITE_FACTORY_API_URL", None)
                step_env.pop("VITE_REGISTRY_API_URL", None)
            step, output = ctx.execute(f"{name}-{label}", command, cwd=folder, env=step_env)
            if label == "vitest":
                match = re.search(r"Tests\s+(\d+) passed", output)
                if step["exit_code"] == 0 and not match:
                    step.update(status="error", exit_code=2, error="NO_FRONTEND_TESTS_EXECUTED")
                elif match:
                    step["metrics"] = {"passed": int(match.group(1))}
            steps.append(step)
        if all(s["status"] == "pass" for s in steps if s["name"].startswith(name + "-")):
            shutil.copytree(folder / "dist", ctx.artifacts / f"{name}-dist", dirs_exist_ok=True)
    return print_result(ctx.finish(steps))


if __name__ == "__main__":
    raise SystemExit(main())
