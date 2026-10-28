"""Deterministic checks for graders using externally defined challenge probes."""

from __future__ import annotations

from dataclasses import dataclass

LABELS = frozenset({"pass", "fail", "uncertain"})
CHALLENGES = frozenset(
    {"reference", "valid_alternative", "seeded_defect", "removed_test", "constant_output"}
)


@dataclass(frozen=True, slots=True)
class GraderProbe:
    case_id: str
    challenge: str
    expected: str
    observed: str
    critical: bool = False


def evaluate_grader_probes(probes: list[GraderProbe], *, run_id: str) -> dict:
    """Score a grader against a controlled probe set without granting authority."""
    if not run_id or not probes:
        raise ValueError("META_GRADER_RUN_REQUIRED")
    ids: set[str] = set()
    for probe in probes:
        if (
            not probe.case_id
            or probe.case_id in ids
            or probe.challenge not in CHALLENGES
            or probe.expected not in LABELS
            or probe.observed not in LABELS
            or type(probe.critical) is not bool
        ):
            raise ValueError("META_GRADER_PROBE_INVALID")
        ids.add(probe.case_id)

    expected_challenges = CHALLENGES - {"constant_output"}
    present_challenges = {probe.challenge for probe in probes}
    alternatives = sum(probe.challenge == "valid_alternative" for probe in probes)
    correct = sum(probe.expected == probe.observed for probe in probes)
    critical_false_accepts = [
        probe.case_id
        for probe in probes
        if probe.critical and probe.expected != "pass" and probe.observed == "pass"
    ]
    constant_output = len({probe.observed for probe in probes}) == 1
    accuracy = correct / len(probes)
    missing_challenges = sorted(expected_challenges - present_challenges)
    missing_alternative_controls = max(0, 2 - alternatives)
    passed = (
        accuracy >= 0.9
        and not critical_false_accepts
        and not constant_output
        and not missing_challenges
        and missing_alternative_controls == 0
    )
    return {
        "schema": 1,
        "run_id": run_id,
        "probes": len(probes),
        "accuracy": accuracy,
        "false_accepts": sum(
            probe.expected != "pass" and probe.observed == "pass" for probe in probes
        ),
        "false_rejections": sum(
            probe.expected == "pass" and probe.observed != "pass" for probe in probes
        ),
        "critical_false_accepts": critical_false_accepts,
        "constant_output_detected": constant_output,
        "missing_challenges": missing_challenges,
        "missing_valid_alternative_controls": missing_alternative_controls,
        "promotion_authorized": False,
        "status": "pass" if passed else "fail",
    }
