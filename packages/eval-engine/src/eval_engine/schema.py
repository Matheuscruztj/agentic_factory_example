"""Typed, deterministic evaluation records and objective metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from statistics import median
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    profile: str
    split: str
    expected_verdict: str
    deterministic_checks: tuple[str, ...]
    critical: bool = False


@dataclass(frozen=True)
class EvalObservation:
    case_id: str
    persona: str
    model: str
    prompt_hash: str
    context_hash: str
    skill_hash: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    checks: dict[str, bool]
    accepted: bool
    evidence_refs: tuple[str, ...] = ()


def validate_observation(value: EvalObservation) -> list[str]:
    errors = []
    for name in ("prompt_hash", "context_hash", "skill_hash"):
        if len(getattr(value, name)) != 64 or any(
            character not in "0123456789abcdef" for character in getattr(value, name)
        ):
            errors.append(f"{name.upper()}_INVALID")
    if value.latency_ms < 0 or value.input_tokens < 0 or value.output_tokens < 0:
        errors.append("MEASUREMENT_NEGATIVE")
    if not isfinite(value.cost_usd) or value.cost_usd < 0:
        errors.append("COST_NEGATIVE")
    if any(not key for key in value.checks):
        errors.append("CHECK_ID_EMPTY")
    if any(type(result) is not bool for result in value.checks.values()):
        errors.append("CHECK_RESULT_INVALID")
    if any(not isinstance(reference, str) or not reference for reference in value.evidence_refs):
        errors.append("EVIDENCE_REFERENCE_INVALID")
    return errors


def build_scorecard(
    cases: list[EvalCase], observations: list[EvalObservation], *, run_id: str
) -> dict[str, Any]:
    case_map = {case.id: case for case in cases}
    relevant = [observation for observation in observations if observation.case_id in case_map]

    def metrics_for(items: list[EvalObservation]) -> dict[str, Any]:
        objective_items = [
            observation
            for observation in items
            if case_map[observation.case_id].deterministic_checks
        ]
        checks_total = sum(
            len(case_map[item.case_id].deterministic_checks) for item in objective_items
        )
        checks_passed = sum(
            item.checks.get(check, False)
            for item in objective_items
            for check in case_map[item.case_id].deterministic_checks
        )
        return {
            "cases": len(items),
            "objective_cases": len(objective_items),
            "objective_checks": checks_total,
            "objective_passed": checks_passed,
            "objective_pass_rate": checks_passed / checks_total if checks_total else None,
            "accepted": sum(item.accepted for item in items),
            "rework": sum(not item.accepted for item in items),
            "median_latency_ms": median(item.latency_ms for item in items) if items else None,
            "input_tokens": sum(item.input_tokens for item in items),
            "output_tokens": sum(item.output_tokens for item in items),
            "cost_usd": round(sum(item.cost_usd for item in items), 8),
        }

    return {
        "schema": 1,
        "run_id": run_id,
        "metrics": metrics_for(relevant),
        "by_persona": {
            persona: metrics_for([item for item in relevant if item.persona == persona])
            for persona in sorted({item.persona for item in relevant})
        },
        "provenance": [
            {
                "case_id": item.case_id,
                "persona": item.persona,
                "model": item.model,
                "prompt_hash": item.prompt_hash,
                "context_hash": item.context_hash,
                "skill_hash": item.skill_hash,
                "evidence_refs": list(item.evidence_refs),
            }
            for item in relevant
        ],
    }


def observation_to_dict(value: EvalObservation) -> dict[str, Any]:
    return asdict(value)
