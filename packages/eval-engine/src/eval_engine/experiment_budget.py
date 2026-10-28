"""Budget provenance and conservative comparability rules for eval trials."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class ResourceProfile:
    profile_id: str
    cpu_cores: float
    memory_mb: int
    vram_mb: int | None
    wall_seconds: int
    concurrency: int
    warmup_runs: int
    cache_policy: str
    model_digest: str
    runner_version: str


def validate_resource_profile(profile: ResourceProfile) -> list[str]:
    errors: list[str] = []
    if not profile.profile_id.strip() or not profile.runner_version.strip():
        errors.append("PROFILE_ID_OR_RUNNER_MISSING")
    if not isfinite(profile.cpu_cores) or profile.cpu_cores <= 0:
        errors.append("CPU_BUDGET_INVALID")
    if profile.memory_mb < 1 or (profile.vram_mb is not None and profile.vram_mb < 1):
        errors.append("MEMORY_BUDGET_INVALID")
    if profile.wall_seconds < 1 or profile.concurrency < 1 or profile.warmup_runs < 0:
        errors.append("TIME_CONCURRENCY_OR_WARMUP_INVALID")
    if profile.cache_policy not in {"cold", "warm", "recorded_mixed"}:
        errors.append("CACHE_POLICY_INVALID")
    if len(profile.model_digest) != 64 or any(
        c not in "0123456789abcdef" for c in profile.model_digest
    ):
        errors.append("MODEL_DIGEST_INVALID")
    return errors


def compare_resource_profiles(baseline: ResourceProfile, candidate: ResourceProfile) -> dict:
    """Only identical experiment conditions are comparable; no hardware scaling."""
    left, right = asdict(baseline), asdict(candidate)
    differences = sorted(key for key in left if left[key] != right[key])
    return {
        "comparable": not differences
        and not validate_resource_profile(baseline)
        and not validate_resource_profile(candidate),
        "differences": differences,
        "classification": "paired_comparable"
        if not differences
        else "inconclusive_configuration_drift",
        "hardware_multiplier_applied": False,
    }


def classify_attempt_failure(
    *,
    profile_valid: bool,
    resource_pressure_observed: bool,
    external_failure: bool,
    strategy_check_failed: bool,
) -> str:
    if external_failure:
        return "infrastructure_external"
    if not profile_valid or resource_pressure_observed:
        return "infrastructure_uncontrolled"
    if strategy_check_failed:
        return "strategy_under_valid_budget"
    return "no_failure_observed"
