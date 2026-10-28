"""Paired, reproducible prompt comparisons; never activate a candidate automatically."""

from __future__ import annotations

import hashlib
import statistics
from collections.abc import Callable
from dataclasses import dataclass

from eval_engine.schema import EvalCase


@dataclass(frozen=True)
class Trial:
    case_id: str
    verdict: str
    critical_failure: bool
    accepted: bool
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class PromptArm:
    name: str
    text: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def compare_prompts(
    *,
    baseline: PromptArm,
    candidate: PromptArm,
    cases: list[EvalCase],
    evaluator: Callable[[PromptArm, EvalCase, int, int], Trial],
    seed: int,
    max_tokens: int,
    minimum_pass_rate_delta: float = 0.02,
) -> dict:
    if (
        not baseline.text.strip()
        or not candidate.text.strip()
        or baseline.sha256 == candidate.sha256
    ):
        raise ValueError("PROMPT_ARMS_MUST_BE_NONEMPTY_AND_DISTINCT")
    if seed < 0 or max_tokens < 1 or not 0 <= minimum_pass_rate_delta <= 1:
        raise ValueError("EXPERIMENT_BUDGET_INVALID")
    baseline_trials = [evaluator(baseline, case, seed, max_tokens) for case in cases]
    candidate_trials = [evaluator(candidate, case, seed, max_tokens) for case in cases]
    if [item.case_id for item in baseline_trials] != [case.id for case in cases] or [
        item.case_id for item in candidate_trials
    ] != [case.id for case in cases]:
        raise ValueError("EVALUATOR_CASE_ORDER_MISMATCH")
    baseline_rate = sum(item.verdict == "pass" for item in baseline_trials) / max(1, len(cases))
    candidate_rate = sum(item.verdict == "pass" for item in candidate_trials) / max(1, len(cases))
    critical_regressions = [
        case.id
        for case, before, after in zip(cases, baseline_trials, candidate_trials, strict=True)
        if case.critical
        and before.verdict == "pass"
        and (after.verdict != "pass" or after.critical_failure)
    ]
    cost_delta = sum(item.cost_usd for item in candidate_trials) - sum(
        item.cost_usd for item in baseline_trials
    )

    def arm_metrics(trials: list[Trial], pass_rate: float) -> dict:
        accepted = sum(item.accepted for item in trials)
        costs = sum(item.cost_usd for item in trials)
        latencies = [item.latency_ms for item in trials]
        return {
            "pass_rate": pass_rate,
            "accepted": accepted,
            "median_latency_ms": statistics.median(latencies) if latencies else None,
            "latency_range_ms": max(latencies) - min(latencies) if latencies else None,
            "input_tokens": sum(item.input_tokens for item in trials),
            "output_tokens": sum(item.output_tokens for item in trials),
            "cost_usd": round(costs, 8),
            "cost_per_accepted_task_usd": round(costs / accepted, 8) if accepted else None,
        }

    eligible = (
        not critical_regressions and candidate_rate >= baseline_rate + minimum_pass_rate_delta
    )
    return {
        "schema": 1,
        "baseline": {
            "name": baseline.name,
            "prompt_hash": baseline.sha256,
            **arm_metrics(baseline_trials, baseline_rate),
        },
        "candidate": {
            "name": candidate.name,
            "prompt_hash": candidate.sha256,
            **arm_metrics(candidate_trials, candidate_rate),
        },
        "comparison": {
            "pass_rate_delta": candidate_rate - baseline_rate,
            "cost_delta_usd": round(cost_delta, 8),
            "critical_regressions": critical_regressions,
            "seed": seed,
            "max_tokens": max_tokens,
        },
        "promotion_eligible": eligible,
        "promotion_decision": "human_review_required" if eligible else "retain_baseline",
        "auto_promoted": False,
        "uncertainty": "Synthetic or evaluator-specific scores are not a human acceptance signal.",
    }
