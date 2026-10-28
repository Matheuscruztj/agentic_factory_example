from eval_engine.meta_grader import GraderProbe, evaluate_grader_probes


def test_meta_grader_checks_alternatives_defects_missing_tests_and_constant_controls():
    probes = [
        GraderProbe("reference-1", "reference", "pass", "pass"),
        GraderProbe("alternative-1", "valid_alternative", "pass", "pass"),
        GraderProbe("alternative-2", "valid_alternative", "pass", "pass"),
        GraderProbe("defect-1", "seeded_defect", "fail", "fail", critical=True),
        GraderProbe("removed-test-1", "removed_test", "uncertain", "uncertain"),
        GraderProbe("constant-control-1", "constant_output", "uncertain", "uncertain"),
    ]

    report = evaluate_grader_probes(probes, run_id="meta-run")

    assert report["status"] == "pass"
    assert report["accuracy"] == 1.0
    assert report["critical_false_accepts"] == []
    assert report["promotion_authorized"] is False


def test_meta_grader_rejects_constant_output_and_critical_false_accept():
    probes = [
        GraderProbe("reference-1", "reference", "pass", "pass"),
        GraderProbe("alternative-1", "valid_alternative", "pass", "pass"),
        GraderProbe("alternative-2", "valid_alternative", "pass", "pass"),
        GraderProbe("defect-1", "seeded_defect", "fail", "pass", critical=True),
        GraderProbe("removed-test-1", "removed_test", "uncertain", "pass"),
        GraderProbe("constant-control-1", "constant_output", "fail", "pass"),
    ]

    report = evaluate_grader_probes(probes, run_id="constant-grader")

    assert report["status"] == "fail"
    assert report["constant_output_detected"] is True
    assert report["critical_false_accepts"] == ["defect-1"]


def test_meta_grader_requires_two_independent_valid_alternative_controls():
    report = evaluate_grader_probes(
        [
            GraderProbe("reference", "reference", "pass", "pass"),
            GraderProbe("alternative", "valid_alternative", "pass", "pass"),
            GraderProbe("defect", "seeded_defect", "fail", "fail", critical=True),
            GraderProbe("removed", "removed_test", "uncertain", "uncertain"),
            GraderProbe("constant", "constant_output", "uncertain", "uncertain"),
        ],
        run_id="one-alternative-only",
    )
    assert report["status"] == "fail"
    assert report["missing_valid_alternative_controls"] == 1
