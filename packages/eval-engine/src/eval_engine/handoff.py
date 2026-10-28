"""Compare continuation strategies against the same authoritative state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HandoffAttempt:
    case_id: str
    strategy: str
    state_sha256: str
    observed_sha256: str
    obligations_total: int
    obligations_lost: int
    effects_expected: int
    effects_observed: int
    reorientation_seconds: float
    context_tokens: int
    large_log_recovery_succeeded: bool


def compare_handoff_attempts(attempts: list[HandoffAttempt]) -> dict:
    if not attempts:
        raise ValueError("HANDOFF_ATTEMPTS_REQUIRED")
    for row in attempts:
        if (
            not row.case_id
            or not row.strategy
            or len(row.state_sha256) != 64
            or len(row.observed_sha256) != 64
            or row.obligations_total < 0
            or row.obligations_lost < 0
            or row.obligations_lost > row.obligations_total
            or row.effects_expected < 0
            or row.effects_observed < 0
            or row.reorientation_seconds < 0
            or row.context_tokens < 0
        ):
            raise ValueError("HANDOFF_ATTEMPT_INVALID")
    case_states: dict[str, set[str]] = {}
    for row in attempts:
        case_states.setdefault(row.case_id, set()).add(row.state_sha256)
    invalid_state_cases = sorted(case for case, states in case_states.items() if len(states) != 1)
    rows = {}
    for strategy in sorted({row.strategy for row in attempts}):
        subset = [row for row in attempts if row.strategy == strategy]
        rows[strategy] = {
            "attempts": len(subset),
            "obligations_lost": sum(row.obligations_lost for row in subset),
            "duplicate_effects": sum(
                max(0, row.effects_observed - row.effects_expected) for row in subset
            ),
            "state_divergences": sum(row.state_sha256 != row.observed_sha256 for row in subset),
            "reorientation_seconds": sum(row.reorientation_seconds for row in subset),
            "context_tokens": sum(row.context_tokens for row in subset),
            "large_log_recoveries": sum(row.large_log_recovery_succeeded for row in subset),
        }
    return {
        "schema": 1,
        "sampling_unit": "case",
        "invalid_state_cases": invalid_state_cases,
        "comparable": not invalid_state_cases,
        "strategies": rows,
        "automatic_promotion": False,
    }
