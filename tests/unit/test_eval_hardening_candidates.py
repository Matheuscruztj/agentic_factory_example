import json
from pathlib import Path

import pytest
from eval_engine.architecture import ArchitectureAttempt, compare_architectures
from eval_engine.experiment_budget import (
    ResourceProfile,
    classify_attempt_failure,
    compare_resource_profiles,
    validate_resource_profile,
)
from eval_engine.handoff import HandoffAttempt, compare_handoff_attempts
from eval_engine.tool_usability import ToolTrial, report_tool_usability

from scripts.validate_eval_catalog import validate_catalog

ROOT = Path(__file__).resolve().parents[2]


def _profile(**overrides):
    values = {
        "profile_id": "local-8gb",
        "cpu_cores": 4,
        "memory_mb": 8192,
        "vram_mb": 8192,
        "wall_seconds": 120,
        "concurrency": 1,
        "warmup_runs": 1,
        "cache_policy": "cold",
        "model_digest": "a" * 64,
        "runner_version": "runner-v1",
    }
    values.update(overrides)
    return ResourceProfile(**values)


def test_suite_catalog_has_explicit_owners_splits_and_no_secret_holdout_claim():
    catalog = json.loads((ROOT / "evals/suite-catalog-v1.json").read_text())
    assert validate_catalog(catalog) == []
    catalog["holdout_claimed"] = True
    assert "DRAFT_DATA_CANNOT_CLAIM_HOLDOUT_OR_PRODUCTION" in validate_catalog(catalog)


def test_resource_profiles_record_budget_and_refuse_drift_or_bad_provenance():
    baseline = _profile()
    assert validate_resource_profile(baseline) == []
    assert compare_resource_profiles(baseline, _profile())["comparable"] is True
    changed = compare_resource_profiles(baseline, _profile(concurrency=2))
    assert changed["classification"] == "inconclusive_configuration_drift"
    assert "concurrency" in changed["differences"]
    assert changed["hardware_multiplier_applied"] is False
    assert "MODEL_DIGEST_INVALID" in validate_resource_profile(_profile(model_digest="unknown"))


def test_failure_classification_separates_infra_from_strategy():
    assert (
        classify_attempt_failure(
            profile_valid=False,
            resource_pressure_observed=True,
            external_failure=False,
            strategy_check_failed=True,
        )
        == "infrastructure_uncontrolled"
    )
    assert (
        classify_attempt_failure(
            profile_valid=True,
            resource_pressure_observed=False,
            external_failure=False,
            strategy_check_failed=True,
        )
        == "strategy_under_valid_budget"
    )


def test_architecture_comparison_pairs_cases_and_counts_coordination_gpu_review_and_rework():
    report = compare_architectures(
        [
            ArchitectureAttempt("case-1", "single", True, executor_seconds=4, tool_calls=2),
            ArchitectureAttempt(
                "case-1",
                "roles",
                True,
                executor_seconds=3,
                coordination_seconds=2,
                gpu_wait_seconds=5,
                review_seconds=2,
                rework_seconds=1,
                tool_calls=5,
            ),
            ArchitectureAttempt("unpaired", "roles", False),
        ]
    )
    assert report["paired_cases"] == ["case-1"]
    assert report["recommendation"] == "inconclusive"
    assert report["metrics"]["roles"]["median_total_seconds"] == 13
    assert report["metrics"]["roles"]["total_gpu_wait_seconds"] == 5
    assert report["automatic_adoption"] is False
    with pytest.raises(ValueError, match="TWO_ARCHITECTURES_REQUIRED"):
        compare_architectures([ArchitectureAttempt("x", "single", True)])


def test_candidate_families_keep_equivalence_groups_together_and_include_non_equivalent_control():
    value = json.loads((ROOT / "evals/design/channel-equivalence-candidates-v1.json").read_text())
    groups = {}
    for row in value["cases"]:
        groups.setdefault(row["family_id"], []).append(row)
    assert {key: len(rows) for key, rows in groups.items()} == {
        "EQUIV-001": 2,
        "EQUIV-002": 2,
        "CONTROL-001": 2,
    }
    for family, rows in groups.items():
        if family.startswith("EQUIV"):
            assert len({json.dumps(row["intent"], sort_keys=True) for row in rows}) == 1
        else:
            assert len({json.dumps(row["intent"], sort_keys=True) for row in rows}) == 2
            assert all(row["equivalent"] is False for row in rows)


def test_fullstack_capability_fixtures_have_no_solution_and_keep_product_decisions_open():
    data = json.loads((ROOT / "evals/fixtures/fullstack-capabilities-v1/manifest.json").read_text())
    assert data["implementation_attempts"] == 0 and data["oracles_frozen"] is False
    assert all(case["solution_files_present"] is False for case in data["cases"])
    assert all(case["product_decisions"] for case in data["cases"])


def test_handoff_comparison_rejects_different_authoritative_states_and_counts_lost_work():
    report = compare_handoff_attempts(
        [
            HandoffAttempt("case-1", "continue", "a" * 64, "a" * 64, 4, 0, 2, 2, 1.0, 20, True),
            HandoffAttempt("case-1", "compact", "a" * 64, "b" * 64, 4, 1, 2, 3, 2.0, 8, False),
        ]
    )
    assert report["comparable"] is True
    assert report["strategies"]["compact"]["obligations_lost"] == 1
    assert report["strategies"]["compact"]["duplicate_effects"] == 1
    assert report["strategies"]["compact"]["state_divergences"] == 1
    assert report["automatic_promotion"] is False
    with pytest.raises(ValueError, match="HANDOFF_ATTEMPT_INVALID"):
        compare_handoff_attempts(
            [HandoffAttempt("case-1", "old", "a" * 64, "a" * 64, 1, 2, 0, 0, 0, 0, True)]
        )


def test_tool_usability_keeps_no_tool_control_and_counts_recovery_without_fixed_order():
    report = report_tool_usability(
        [
            ToolTrial("case-1", "tool", True, True, True, True, True, 2, 1, 30, True),
            ToolTrial("case-1", "no_tool", False, False, True, False, True, 0, 0, 12, True),
        ],
        run_id="tool-trial-1",
    )
    assert report["tool_order_required"] is False
    assert report["metrics_by_arm"]["tool"]["unproductive_calls"] == 1
    assert report["metrics_by_arm"]["no_tool"]["tool_calls"] == 0
    with pytest.raises(ValueError, match="TOOL_TRIAL_INVALID"):
        report_tool_usability(
            [ToolTrial("case-2", "no_tool", True, True, True, True, True, 1, 0, 2, True)],
            run_id="bad-no-tool",
        )


def test_interaction_candidates_have_explicit_effect_oracles_and_negative_controls():
    data = json.loads(
        (ROOT / "evals/design/interaction-and-channel-candidates-v1.json").read_text()
    )
    assert len(data["scenarios"]) == 4
    assert all(row["required_evidence"] and row["negative_control"] for row in data["scenarios"])
