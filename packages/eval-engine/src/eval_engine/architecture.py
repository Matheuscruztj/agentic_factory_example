"""Paired architecture comparison with full effort accounting."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True, slots=True)
class ArchitectureAttempt:
    case_id: str
    architecture: str
    passed: bool
    critical_failure: bool = False
    executor_seconds: float = 0.0
    coordination_seconds: float = 0.0
    gpu_wait_seconds: float = 0.0
    tool_calls: int = 0
    review_seconds: float = 0.0
    rework_seconds: float = 0.0

    @property
    def total_seconds(self) -> float:
        return sum(
            (
                self.executor_seconds,
                self.coordination_seconds,
                self.gpu_wait_seconds,
                self.review_seconds,
                self.rework_seconds,
            )
        )


def compare_architectures(attempts: list[ArchitectureAttempt]) -> dict:
    if not attempts:
        raise ValueError("ARCHITECTURE_ATTEMPTS_REQUIRED")
    if any(not item.case_id or not item.architecture for item in attempts):
        raise ValueError("ARCHITECTURE_ATTEMPT_ID_REQUIRED")
    if any(min(item.total_seconds, item.tool_calls) < 0 for item in attempts):
        raise ValueError("ARCHITECTURE_MEASUREMENT_NEGATIVE")
    by_arch: dict[str, list[ArchitectureAttempt]] = {}
    pairs: dict[str, set[str]] = {}
    for row in attempts:
        by_arch.setdefault(row.architecture, []).append(row)
        pairs.setdefault(row.case_id, set()).add(row.architecture)
    if len(by_arch) < 2:
        raise ValueError("TWO_ARCHITECTURES_REQUIRED")
    common_cases = {case for case, names in pairs.items() if names >= set(by_arch)}
    metrics = {}
    for name, rows in sorted(by_arch.items()):
        paired = [row for row in rows if row.case_id in common_cases]
        metrics[name] = {
            "attempts": len(rows),
            "paired_cases": len(paired),
            "pass_rate": sum(row.passed for row in paired) / len(paired) if paired else None,
            "critical_failures": sum(row.critical_failure for row in paired),
            "median_total_seconds": median(row.total_seconds for row in paired) if paired else None,
            "total_gpu_wait_seconds": sum(row.gpu_wait_seconds for row in paired),
            "total_review_seconds": sum(row.review_seconds for row in paired),
            "total_rework_seconds": sum(row.rework_seconds for row in paired),
            "total_tool_calls": sum(row.tool_calls for row in paired),
        }
    return {
        "schema": 1,
        "sampling_unit": "paired_case",
        "paired_cases": sorted(common_cases),
        "metrics": metrics,
        "recommendation": "inconclusive" if len(common_cases) < 20 else "review_required",
        "automatic_adoption": False,
    }
