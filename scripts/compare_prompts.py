#!/usr/bin/env python3
"""Analyze paired prompt trials produced by an approved local evaluator."""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path

from eval_engine.experiments import PromptArm, Trial, compare_prompts
from eval_engine.schema import EvalCase

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--observations",
        type=Path,
        required=True,
        help="Paired observations JSON emitted by an evaluator",
    )
    parser.add_argument(
        "--baseline", type=Path, default=Path("agents/prompts/feature-baseline-v1.md")
    )
    parser.add_argument(
        "--candidate", type=Path, default=Path("agents/prompts/feature-candidate-v1.md")
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/fixtures/regression/cases.json")
    )
    args = parser.parse_args()
    observations = json.loads(args.observations.read_text(encoding="utf-8"))
    dataset = json.loads((ROOT / args.dataset).read_text(encoding="utf-8"))
    cases = [
        EvalCase(
            case["id"],
            case["profile"],
            dataset["split"],
            case["expected_verdict"],
            tuple(case["deterministic_checks"]),
            case.get("critical", False),
        )
        for case in dataset["cases"]
    ]
    arms = {
        "baseline": PromptArm("baseline", (ROOT / args.baseline).read_text(encoding="utf-8")),
        "candidate": PromptArm("candidate", (ROOT / args.candidate).read_text(encoding="utf-8")),
    }
    trial_map = {
        (item["arm"], item["case_id"]): Trial(
            case_id=item["case_id"],
            verdict=item["verdict"],
            critical_failure=bool(item.get("critical_failure", False)),
            accepted=bool(item["accepted"]),
            latency_ms=int(item["latency_ms"]),
            input_tokens=int(item["input_tokens"]),
            output_tokens=int(item["output_tokens"]),
            cost_usd=float(item["cost_usd"]),
        )
        for item in observations["trials"]
    }

    def evaluator(arm: PromptArm, case: EvalCase, _seed: int, _budget: int) -> Trial:
        try:
            return trial_map[(arm.name, case.id)]
        except KeyError as exc:
            raise ValueError("PAIRED_TRIAL_MISSING") from exc

    report = compare_prompts(
        baseline=arms["baseline"],
        candidate=arms["candidate"],
        cases=cases,
        evaluator=evaluator,
        seed=int(observations["seed"]),
        max_tokens=int(observations["max_tokens"]),
    )
    report["dataset"] = {
        "id": dataset["dataset"],
        "split": dataset["split"],
        "label_source": observations.get("label_source", "unspecified"),
    }
    report["prompt_diff"] = list(
        difflib.unified_diff(
            arms["baseline"].text.splitlines(),
            arms["candidate"].text.splitlines(),
            fromfile=arms["baseline"].name,
            tofile=arms["candidate"].name,
            lineterm="",
        )
    )
    report["experiment_id"] = observations.get("experiment_id")
    report["check"] = "prompt-experiment"
    report["status"] = "pass"
    report["ok"] = 1
    report["exit_code"] = 0
    report["artifact"] = ".runtime/evals/prompt-experiment.json"
    report["errors"] = []
    report["auto_promoted"] = False
    artifact = ROOT / ".runtime/evals/prompt-experiment.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
