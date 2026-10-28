import pytest
from eval_engine.synthetic_judge import cases, evaluate, reference


def test_reference_is_derived_from_probe_and_missing_evidence_abstains():
    assert reference({"claimed": 2, "evidence": {"observed": 2}}) == "pass"
    assert reference({"claimed": 2, "evidence": {"observed": 1}}) == "fail"
    assert reference({"claimed": 2, "evidence": {"observed": None}}) == "uncertain"


def test_dataset_is_reproducible_and_cosmetic_variants_keep_reference():
    dataset = cases()
    assert dataset == cases()
    assert len(dataset) == 63
    assert {item["reference"] for item in dataset} == {"pass", "fail", "uncertain"}
    result = evaluate(dataset, [{"id": x["id"], "verdict": x["reference"]} for x in dataset])
    assert result["metrics"]["accuracy"] == 1
    assert result["metrics"]["critical_false_negatives"] == 0
    assert result["human_agreement"] is None
    assert result["promotion_eligible"] is False


def test_approving_everything_exposes_critical_misses_and_advisory_conclusion():
    dataset = cases()
    result = evaluate(dataset, [{"id": x["id"], "verdict": "pass"} for x in dataset])
    assert result["evaluation_complete"]
    assert result["conclusion"] == "advisory_only"
    assert result["metrics"]["critical_false_negatives"] == 21


def test_incomplete_or_duplicated_judgments_cannot_complete_characterization():
    dataset = cases()
    with pytest.raises(ValueError, match="COVERAGE_INVALID"):
        evaluate(dataset, [])
    judgments = [{"id": x["id"], "verdict": "pass"} for x in dataset]
    with pytest.raises(ValueError, match="COVERAGE_INVALID"):
        evaluate(dataset, judgments + judgments[:1])
