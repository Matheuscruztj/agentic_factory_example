from eval_engine.reliability import ReliabilityAttempt, reliability_report
from eval_engine.schema import EvalCase, EvalObservation, build_scorecard, validate_observation


def test_scorecard_keeps_deterministic_metrics_separate_from_judge_scores():
    case = EvalCase("case-1", "backend", "regression", "pass", ("tests_pass",))
    observation = EvalObservation(
        case_id="case-1",
        persona="backend",
        model="executor-a",
        prompt_hash="a" * 64,
        context_hash="b" * 64,
        skill_hash="c" * 64,
        latency_ms=120,
        input_tokens=50,
        output_tokens=12,
        cost_usd=0.001,
        checks={"tests_pass": True},
        accepted=True,
        evidence_refs=("artifact:abc",),
    )

    report = build_scorecard([case], [observation], run_id="run-1")

    assert not validate_observation(observation)
    assert report["metrics"]["objective_pass_rate"] == 1.0
    assert report["metrics"]["median_latency_ms"] == 120
    assert "judge_score" not in report["metrics"]


def test_unmeasured_objective_checks_do_not_receive_a_subjective_score():
    report = build_scorecard([], [], run_id="run-empty")
    assert report["metrics"]["objective_pass_rate"] is None


def test_scorecard_reports_metrics_per_persona():
    backend = EvalCase("backend-case", "backend", "dev", "pass", ("tests",))
    qa = EvalCase("qa-case", "qa", "dev", "pass", ("review",))
    observations = [
        EvalObservation("backend-case", "backend", "model-a", "a" * 64, "b" * 64,
                        "c" * 64, 100, 1, 2, 0.1, {"tests": True}, True),
        EvalObservation("qa-case", "qa", "model-b", "d" * 64, "e" * 64,
                        "f" * 64, 200, 3, 4, 0.2, {"review": False}, False),
    ]

    report = build_scorecard([backend, qa], observations, run_id="run-profiles")

    assert report["by_persona"]["backend"]["objective_pass_rate"] == 1.0
    assert report["by_persona"]["qa"]["objective_pass_rate"] == 0.0


def test_reliability_uses_case_macro_and_correct_repeated_sample_estimators():
    rows = [
        ReliabilityAttempt("case-a", "a1", "backend", True, cost_usd=0.1),
        ReliabilityAttempt("case-a", "a2", "backend", True, internal_corrections=1),
        ReliabilityAttempt("case-a", "a3", "backend", False),
        ReliabilityAttempt("case-b", "b1", "backend", True),
        ReliabilityAttempt("case-b", "b2", "backend", False),
        ReliabilityAttempt("case-b", "b3", "backend", False),
    ]

    result = reliability_report(rows, run_id="paired-run", k=2, seed=17)

    assert result["sampling_unit"] == "case"
    assert result["metrics"]["cases"] == 2
    assert result["metrics"]["external_attempts"] == 6
    assert result["metrics"]["internal_corrections"] == 1
    assert result["metrics"]["pass_at_1"] == 0.5
    assert result["metrics"]["pass_at_k"] == 5 / 6
    assert result["metrics"]["pass_pow_k"] == 1 / 6
    assert result["metrics"]["cost_usd"] == 0.1
    assert result["metrics"]["cost_observations"] == 1
    assert result["metrics"]["pass_at_1_ci95"] is None
    assert result["metrics"]["insufficient_sample_for_ci"] is True


def test_reliability_rejects_duplicate_attempt_identity():
    attempt = ReliabilityAttempt("case-a", "attempt-1", "backend", True)
    try:
        reliability_report([attempt, attempt], run_id="duplicate-run")
    except ValueError as exc:
        assert str(exc) == "DUPLICATE_RELIABILITY_ATTEMPT"
    else:
        raise AssertionError("duplicate attempt should be rejected")


def test_reliability_records_paired_attempt_provenance():
    rows = [
        ReliabilityAttempt(
            "case-a", "baseline-1", "baseline", True,
            baseline_id="base-v1", configuration_hash="a" * 64,
            reset_id="reset-1", pair_id="pair-1",
        ),
        ReliabilityAttempt(
            "case-a", "candidate-1", "candidate", True,
            baseline_id="base-v1", configuration_hash="b" * 64,
            reset_id="reset-1", pair_id="pair-1",
        ),
    ]

    result = reliability_report(rows, run_id="paired", k=1)

    assert result["metrics"]["attempts_with_complete_provenance"] == 2
    assert result["metrics"]["attempts_missing_provenance"] == 0
    assert result["metrics"]["paired_case_groups"] == 1


def test_reliability_requires_full_provenance_for_paired_attempts():
    row = ReliabilityAttempt("case-a", "a1", "baseline", True, pair_id="pair-1")
    try:
        reliability_report([row], run_id="incomplete-pair")
    except ValueError as exc:
        assert str(exc) == "INVALID_RELIABILITY_ATTEMPT"
    else:
        raise AssertionError("paired attempt without reset/config provenance should fail")


def test_reliability_does_not_count_repeated_same_arm_as_a_pair():
    rows = [
        ReliabilityAttempt(
            "case-a", "a1", "baseline", True, baseline_id="base",
            configuration_hash="a" * 64, reset_id="reset", pair_id="pair",
        ),
        ReliabilityAttempt(
            "case-a", "a2", "baseline", False, baseline_id="base",
            configuration_hash="a" * 64, reset_id="reset", pair_id="pair",
        ),
    ]

    report = reliability_report(rows, run_id="not-paired")

    assert report["metrics"]["paired_case_groups"] == 0
    assert report["metrics"]["incomplete_pair_groups"] == 1


def test_reliability_bootstrap_is_seeded_and_uses_independent_cases():
    rows = [
        ReliabilityAttempt(
            f"case-{case}", f"attempt-{case}-{replica}", "backend", replica == 0
        )
        for case in range(20)
        for replica in range(2)
    ]

    first = reliability_report(rows, run_id="ci-run", k=2, seed=23)
    second = reliability_report(rows, run_id="ci-run", k=2, seed=23)

    assert first["metrics"]["cases"] == 20
    assert first["metrics"]["attempts"] == 40
    assert first["metrics"]["pass_at_1_ci95"] == second["metrics"]["pass_at_1_ci95"]
    assert first["metrics"]["pass_at_1_ci95"] is not None
    assert first["metrics"]["insufficient_sample_for_ci"] is False
