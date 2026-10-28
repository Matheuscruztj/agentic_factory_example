#!/usr/bin/env python3
"""Run report-only local Ollama judge calibration; never changes gates."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/eval-engine/src"))
from eval_engine.judge import JudgeError, OllamaJudge, calibration_metrics

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals/fixtures/judge-calibration-v1.json"
ARTIFACT = ROOT / ".runtime/evals/judge-calibration.json"
RUBRIC = json.loads((ROOT / "evals/rubrics/judge-v1.json").read_text(encoding="utf-8"))


def main() -> int:
    judge_model = os.getenv("EVAL_JUDGE_MODEL", "qwen3:4b")
    executor_model = os.getenv("EVAL_EXECUTOR_MODEL", "qwen2.5-coder:7b")
    base_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    judge = OllamaJudge(base_url=base_url, model=judge_model)
    judged = []
    errors = []
    details = []
    try:
        for case in fixture["cases"]:
            verdict = judge.judge(
                executor_model=executor_model,
                answer=case["answer"],
                evidence=case["evidence"],
                rubric=RUBRIC,
            )
            judged.append(verdict.verdict)
            details.append(
                {
                    "case_id": case["id"],
                    "verdict": verdict.verdict,
                    "score": verdict.score,
                    "confidence": verdict.confidence,
                    "evidence_refs": list(verdict.evidence_refs),
                    "human_review_required": verdict.human_review_required,
                }
            )
    except JudgeError as exc:
        errors.append(str(exc))
    except OSError:
        errors.append("OLLAMA_UNAVAILABLE")
    if len(judged) == len(fixture["cases"]):
        metrics = calibration_metrics([case["gold"] for case in fixture["cases"]], judged)
        meets_calibration = (
            metrics["accuracy"] >= 0.8
            and metrics["false_positive_rate"] <= 0.1
            and metrics["recall"] >= 0.95
        )
        status = "pass" if meets_calibration else "fail"
        code = 0 if meets_calibration else 1
    else:
        metrics = {"cases": len(judged), "expected_cases": len(fixture["cases"])}
        status = "error"
        code = 2
    result = {
        "schema": 1,
        "check": "judge-calibration",
        "status": status,
        "ok": int(code == 0),
        "exit_code": code,
        "metrics": metrics,
        "judge_model": judge_model,
        "executor_model": executor_model,
        "label_source": fixture["label_source"],
        "human_review_required": True,
        "approval_or_gate_mutated": False,
        "judgments": details,
        "artifact": ".runtime/evals/judge-calibration.json",
        "errors": errors,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
