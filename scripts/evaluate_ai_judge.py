#!/usr/bin/env python3
"""Run the independent binary Judge while counting parse failures explicitly."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/eval-engine/src"))
from eval_engine.judge import JudgeError, OllamaJudge  # type: ignore[import-untyped]  # noqa: E402


def evaluate(
    *,
    cases: list[dict],
    judge_model: str,
    executor_model: str,
    base_url: str = "http://127.0.0.1:11434",
) -> dict:
    judge = OllamaJudge(base_url=base_url, model=judge_model)
    results = []
    counts = {
        "invalid_json": 0,
        "invalid_evidence": 0,
        "infra_errors": 0,
        "reviewed": 0,
        "uncertain": 0,
    }
    for case in cases:
        try:
            verdict = judge.accept(
                executor_model=executor_model,
                answer=case["answer"],
                evidence=case.get("evidence", {}),
                rubric={
                    "policy": [
                        "No score without sufficient evidence.",
                        "Missing evidence must remain uncertain.",
                        "Cite only supplied evidence keys.",
                    ]
                },
            )
        except JudgeError as exc:
            code = str(exc)
            if code == "JUDGE_RESPONSE_INVALID":
                counts["invalid_json"] += 1
                category = "invalid_json"
            elif code in {"UNKNOWN_EVIDENCE_REFERENCE", "EVIDENCE_REFS_INVALID"}:
                counts["invalid_evidence"] += 1
                category = "invalid_evidence"
            else:
                counts["infra_errors"] += 1
                category = "judge_error"
            results.append({"case_id": case["id"], "error_class": category, "error_code": code})
            continue
        counts["reviewed"] += 1
        counts["uncertain"] += verdict.verdict == "uncertain"
        results.append(
            {
                "case_id": case["id"],
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "evidence_refs": list(verdict.evidence_refs),
                "human_review_required": verdict.human_review_required,
                "prompt_sha256": verdict.prompt_sha256,
                "response_sha256": verdict.response_sha256,
            }
        )
    return {
        "schema": 1,
        "judge_model": judge_model,
        "executor_model": executor_model,
        "review_protocol": "binary_acceptance_no_score",
        "counts": counts,
        "results": results,
        "status": "pass"
        if not any(counts[k] for k in ("invalid_json", "invalid_evidence", "infra_errors"))
        else "incomplete",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/fixtures/judge-calibration-v1.json")
    )
    parser.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL", "qwen3:4b"))
    parser.add_argument(
        "--executor-model", default=os.getenv("EVAL_EXECUTOR_MODEL", "qwen2.5-coder:7b")
    )
    parser.add_argument("--ollama-url", default=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/evals/binary-judge.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({"check": "binary-ai-judge", "ok": 1, "inference": False}))
        return 0
    try:
        dataset = json.loads(args.dataset.read_text())
        cases = dataset["cases"]
        report = evaluate(
            cases=cases,
            judge_model=args.judge_model,
            executor_model=args.executor_model,
            base_url=args.ollama_url,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"check": "binary-ai-judge", "ok": 0, "error": type(exc).__name__}))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "check": "binary-ai-judge",
                "ok": int(report["status"] == "pass"),
                "counts": report["counts"],
                "report": str(args.output),
            }
        )
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
