"""Case-level reliability metrics for repeated agent attempts."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, slots=True)
class ReliabilityAttempt:
    case_id: str
    attempt_id: str
    profile: str
    passed: bool
    external_attempts: int = 1
    internal_corrections: int = 0
    cost_usd: float | None = None
    baseline_id: str | None = None
    configuration_hash: str | None = None
    reset_id: str | None = None
    pair_id: str | None = None


def _case_scores(rows: list[ReliabilityAttempt], k: int) -> list[float]:
    by_case: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_case[row.case_id].append(row.passed)
    scores = []
    for outcomes in by_case.values():
        n = len(outcomes)
        c = sum(outcomes)
        if n < k:
            continue
        denominator = math.comb(n, k)
        if k == 1:
            scores.append(c / n)
        elif k > 1:
            probability_at_least_one = 1 - math.comb(n - c, k) / denominator
            scores.append(probability_at_least_one)
    return scores


def _pass_all_scores(rows: list[ReliabilityAttempt], k: int) -> list[float]:
    by_case: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        by_case[row.case_id].append(row.passed)
    scores = []
    for outcomes in by_case.values():
        n = len(outcomes)
        c = sum(outcomes)
        if n >= k:
            scores.append(math.comb(c, k) / math.comb(n, k) if c >= k else 0.0)
    return scores


def _interval(values: list[float], *, seed: int, resamples: int = 2000) -> list[float] | None:
    # The independent sampling unit is a case, not an individual attempt.
    if len(values) < 20:
        return None
    estimates = []
    for sample_number in range(resamples):
        sample = []
        for draw_number in range(len(values)):
            material = f"{seed}:{sample_number}:{draw_number}".encode()
            index = int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % len(values)
            sample.append(values[index])
        estimates.append(mean(sample))
    estimates.sort()
    return [estimates[int(0.025 * (resamples - 1))], estimates[int(0.975 * (resamples - 1))]]


def _summarize(rows: list[ReliabilityAttempt], *, seed: int, k: int) -> dict:
    scores_at_1 = _case_scores(rows, 1)
    scores_at_k = _case_scores(rows, k)
    scores_all_k = _pass_all_scores(rows, k)
    measured_costs = [row.cost_usd for row in rows if row.cost_usd is not None]
    complete_provenance = [
        row
        for row in rows
        if row.baseline_id and row.configuration_hash and row.reset_id
    ]
    pair_groups: dict[tuple[str, str], list[ReliabilityAttempt]] = defaultdict(list)
    for row in rows:
        if row.pair_id:
            pair_groups[(row.case_id, row.pair_id)].append(row)
    complete_pairs = [
        group
        for group in pair_groups.values()
        if len({row.profile for row in group}) >= 2
        and len({row.baseline_id for row in group}) == 1
        and len({row.reset_id for row in group}) == 1
    ]
    return {
        "cases": len({row.case_id for row in rows}),
        "attempts": len(rows),
        "external_attempts": sum(row.external_attempts for row in rows),
        "internal_corrections": sum(row.internal_corrections for row in rows),
        "passed_attempts": sum(row.passed for row in rows),
        "pass_at_1": mean(scores_at_1) if scores_at_1 else None,
        "pass_at_1_ci95": _interval(scores_at_1, seed=seed),
        "pass_at_k": mean(scores_at_k) if scores_at_k else None,
        "pass_at_k_cases": len(scores_at_k),
        "pass_at_k_ci95": _interval(scores_at_k, seed=seed + 1),
        "pass_pow_k": mean(scores_all_k) if scores_all_k else None,
        "pass_pow_k_cases": len(scores_all_k),
        "pass_pow_k_ci95": _interval(scores_all_k, seed=seed + 2),
        "cost_usd": round(sum(measured_costs), 8) if measured_costs else None,
        "cost_observations": len(measured_costs),
        "attempts_with_complete_provenance": len(complete_provenance),
        "attempts_missing_provenance": len(rows) - len(complete_provenance),
        "paired_case_groups": len(complete_pairs),
        "incomplete_pair_groups": len(pair_groups) - len(complete_pairs),
        "insufficient_sample_for_ci": len(scores_at_1) < 20,
    }


def reliability_report(
    attempts: list[ReliabilityAttempt], *, run_id: str, k: int = 2, seed: int = 0
) -> dict:
    """Report case-macro pass@k/pass^k without treating missing costs as zero."""
    if not run_id or k < 1 or seed < 0:
        raise ValueError("INVALID_RELIABILITY_REPORT_REQUEST")
    seen: set[tuple[str, str]] = set()
    for row in attempts:
        if (
            not row.case_id
            or not row.attempt_id
            or not row.profile
            or type(row.passed) is not bool
            or row.external_attempts < 1
            or row.internal_corrections < 0
            or (row.cost_usd is not None and (not math.isfinite(row.cost_usd) or row.cost_usd < 0))
            or any(
                value is not None and not value.strip()
                for value in (
                    row.baseline_id,
                    row.configuration_hash,
                    row.reset_id,
                    row.pair_id,
                )
            )
            or (
                row.pair_id is not None
                and not all((row.baseline_id, row.configuration_hash, row.reset_id))
            )
        ):
            raise ValueError("INVALID_RELIABILITY_ATTEMPT")
        key = (row.case_id, row.attempt_id)
        if key in seen:
            raise ValueError("DUPLICATE_RELIABILITY_ATTEMPT")
        seen.add(key)
    by_profile = {
        profile: _summarize([row for row in attempts if row.profile == profile], seed=seed, k=k)
        for profile in sorted({row.profile for row in attempts})
    }
    return {
        "schema": 1,
        "run_id": run_id,
        "sampling_unit": "case",
        "k": k,
        "metrics": _summarize(attempts, seed=seed, k=k),
        "by_profile": by_profile,
        "uncertainty": (
            "Bootstrap intervals use independent cases; "
            "fewer than 20 cases is insufficient."
        ),
    }
