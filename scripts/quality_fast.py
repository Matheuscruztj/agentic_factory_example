#!/usr/bin/env python3
"""Fast local loop: lint, type/build contracts, and deterministic/local agent evals."""

from __future__ import annotations

import fcntl
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.quality_common import QUALITY, QualityContext, print_result, source_manifest  # noqa: E402
from scripts.validate_env import read_env  # noqa: E402


def _parse_json(output: str) -> dict | None:
    try:
        result = json.loads(output)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


def main() -> int:
    QUALITY.mkdir(parents=True, exist_ok=True)
    with (QUALITY / "runner-fast.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return print_result({
                "schema": 1, "check": "quality-fast", "status": "error", "ok": 0,
                "exit_code": 2, "metrics": {}, "artifact": None,
                "errors": ["QUALITY_FAST_ALREADY_ACTIVE"],
            })
        ctx = QualityContext("quality-fast")
        steps: list[dict] = []
        for name, folder in (
            ("factory", ROOT / "apps/factory-web"),
            ("registry", ROOT / "apps/customer-registry/web"),
        ):
            for label, command in (
                ("lint", ["pnpm", "lint"]),
                ("typecheck", ["pnpm", "typecheck"]),
                ("build", ["pnpm", "build"]),
            ):
                env = ctx.environment()
                if label == "build":
                    env["VITE_FACTORY_API_URL"] = "http://127.0.0.1:18801"
                    env["VITE_REGISTRY_API_URL"] = "http://127.0.0.1:18810"
                else:
                    env.pop("VITE_FACTORY_API_URL", None)
                    env.pop("VITE_REGISTRY_API_URL", None)
                step, _ = ctx.execute(f"{name}-{label}", command, cwd=folder, env=env)
                steps.append(step)

        steps.append(
            ctx.execute(
                "python-lint",
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "apps",
                    "packages",
                    "workers",
                    "scripts",
                    "tests",
                ],
            )[0]
        )
        steps.append(ctx.execute(
            "openapi-contract",
            [sys.executable, "scripts/gen_client.py", "--check"],
        )[0])
        datasets_step, datasets_output = ctx.execute(
            "eval-datasets",
            [sys.executable, "scripts/validate_eval_datasets.py"],
            json_output=True,
        )
        steps.append(datasets_step)
        datasets_result = _parse_json(datasets_output)
        if datasets_step["status"] == "pass" and (
            datasets_result is None or datasets_result.get("check") != "eval-datasets"
        ):
            datasets_step.update(status="error", exit_code=2, error="EVAL_DATASET_RESULT_INVALID")

        context_step, context_output = ctx.execute(
            "context-eval",
            [sys.executable, "scripts/evaluate_context.py"],
            json_output=True,
        )
        steps.append(context_step)
        context_result = _parse_json(context_output)
        if context_step["status"] == "pass" and (
            context_result is None or context_result.get("check") != "context-eval"
        ):
            context_step.update(status="error", exit_code=2, error="CONTEXT_EVAL_RESULT_INVALID")

        eval_env = ctx.environment()
        env_file = ROOT / ".env"
        if env_file.is_file():
            cfg = read_env(env_file)
            eval_env.update({
                "OLLAMA_URL": cfg.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                "EVAL_JUDGE_MODEL": cfg.get("OLLAMA_MODEL_JUDGE")
                or cfg.get("OLLAMA_MODEL_CHAT", "qwen3:4b"),
                "EVAL_EXECUTOR_MODEL": cfg.get("OLLAMA_MODEL_CODING", "qwen2.5-coder:7b"),
            })
        judge_step, judge_output = ctx.execute(
            "judge-calibration",
            [sys.executable, "scripts/evaluate_judge.py"],
            timeout=900,
            env=eval_env,
            json_output=True,
        )
        steps.append(judge_step)
        judge_result = _parse_json(judge_output)
        if judge_step["status"] == "pass" and (
            judge_result is None or judge_result.get("check") != "judge-calibration"
        ):
            judge_step.update(status="error", exit_code=2, error="JUDGE_EVAL_RESULT_INVALID")

        if source_manifest()["source_sha256"] != ctx.manifest["source_sha256"]:
            steps.append({
                "name": "source-stability", "status": "error", "exit_code": 2,
                "error": "SOURCE_CHANGED_DURING_QUALITY_FAST",
            })
        result = ctx.finish(steps, profile="fast", includes=["lint", "typecheck", "build", "evals"])
        return print_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
