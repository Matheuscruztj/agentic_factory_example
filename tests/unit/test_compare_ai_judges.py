from __future__ import annotations

from scripts.compare_ai_judges import compare


def test_comparison_emits_confusion_divergence_critical_miss_and_no_fake_human_agreement(tmp_path):
    train = tmp_path / "train.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    train.write_text('{"id":"a","severity":"critical"}\n{"id":"b","severity":"major"}\n')
    holdout.write_text('{"id":"c","severity":"critical"}\n')
    source = {
        "dataset": "synthetic-v1",
        "review_protocol": "dual-ai",
        "train": {
            "labels": {"a": "fail", "b": "pass"},
            "reviewers": {
                "judge-a": {
                    "latency_ms": 10,
                    "metrics": {},
                    "reviews": [{"id": "a", "verdict": "pass"}, {"id": "b", "verdict": "pass"}],
                },
                "judge-b": {
                    "latency_ms": 20,
                    "metrics": {},
                    "reviews": [{"id": "a", "verdict": "fail"}, {"id": "b", "verdict": "pass"}],
                },
            },
        },
        "holdout": {
            "labels": {"c": "uncertain"},
            "reviewers": {
                "judge-a": {
                    "latency_ms": 11,
                    "metrics": {},
                    "reviews": [{"id": "c", "verdict": "uncertain"}],
                },
                "judge-b": {
                    "latency_ms": 21,
                    "metrics": {},
                    "reviews": [{"id": "c", "verdict": "uncertain"}],
                },
            },
        },
    }
    report = compare(source, train_path=train, holdout_path=holdout)
    assert (
        report["splits"]["train"]["reviewers"]["judge-a"]["confusion_matrix"]["fail"]["pass"] == 1
    )
    assert report["splits"]["train"]["reviewers"]["judge-a"]["critical_false_negative_ids"] == ["a"]
    assert report["splits"]["train"]["reviewers"]["judge-a"]["rates"] == {
        "judgments": 2,
        "coverage": 1.0,
        "abstentions": 0,
        "false_rejects": 0,
        "false_reject_denominator": 1,
        "false_reject_rate": 0.0,
        "critical_false_negatives": 1,
        "critical_positive_denominator": 1,
        "critical_false_negative_rate": 1.0,
    }
    assert report["splits"]["train"]["divergences"] == [
        {"case_id": "a", "expected": "fail", "judge-a": "pass", "judge-b": "fail"}
    ]
    assert report["splits"]["holdout"]["human_agreement"] is None
    assert report["promotion_eligible"] is False


def test_comparison_rejects_missing_judge_case_and_invalid_label(tmp_path):
    import pytest

    train = tmp_path / "train.jsonl"
    holdout = tmp_path / "holdout.jsonl"
    train.write_text('{"id":"a","severity":"critical"}\n', encoding="utf-8")
    holdout.write_text('{"id":"b","severity":"major"}\n', encoding="utf-8")
    source = {
        "dataset": "synthetic-v1",
        "review_protocol": "dual-ai",
        "train": {
            "labels": {"a": "fail"},
            "reviewers": {
                "judge-a": {"metrics": {}, "reviews": []},
                "judge-b": {"metrics": {}, "reviews": [{"id": "a", "verdict": "fail"}]},
            },
        },
        "holdout": {
            "labels": {"b": "unexpected"},
            "reviewers": {
                "judge-a": {"metrics": {}, "reviews": [{"id": "b", "verdict": "pass"}]},
                "judge-b": {"metrics": {}, "reviews": [{"id": "b", "verdict": "pass"}]},
            },
        },
    }
    with pytest.raises(ValueError, match="JUDGE_REVIEW_COVERAGE_INVALID"):
        compare(source, train_path=train, holdout_path=holdout)

    source["train"]["reviewers"]["judge-a"]["reviews"] = [{"id": "a", "verdict": "pass"}]
    with pytest.raises(ValueError, match="JUDGE_LABEL_COVERAGE_INVALID"):
        compare(source, train_path=train, holdout_path=holdout)
