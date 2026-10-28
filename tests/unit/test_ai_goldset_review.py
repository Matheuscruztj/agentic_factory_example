from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_ai_goldset


def test_review_prompt_omits_expected_labels_and_split(monkeypatch):
    case = {
        "id": "case-a1b2c3d4",
        "profile": "security",
        "severity": "critical",
        "expected_label": "fail",
        "split": "holdout",
        "answer": "claim",
        "evidence": {"artifact:test": "failed"},
    }
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        @staticmethod
        def json():
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "reviews": [
                                {
                                    "id": case["id"],
                                    "verdict": "fail",
                                    "confidence": 0.9,
                                    "evidence_refs": ["artifact:test"],
                                }
                            ]
                        }
                    )
                }
            }

    def post(_url, *, json, **_kwargs):
        captured.update(json)
        return Response()

    monkeypatch.setattr(verify_ai_goldset.httpx, "post", post)
    result = verify_ai_goldset._review("http://127.0.0.1:11434", "judge", [case])
    prompt = captured["messages"][0]["content"]
    assert "expected_label" not in prompt and "holdout" not in prompt
    assert result[0]["verdict"] == "fail"


def test_verification_requires_two_distinct_models_and_keeps_holdout_separate(
    tmp_path, monkeypatch
):
    train = verify_ai_goldset.load_cases(Path("evals/goldsets/judge-candidates-v1.jsonl"))
    holdout = verify_ai_goldset.load_cases(Path("evals/hidden/judge-holdout-v1.jsonl"))
    assert len(train) == 18 and len(holdout) == 6
    assert not ({item["id"] for item in train} & {item["id"] for item in holdout})
    with pytest.raises(ValueError, match="TWO_DISTINCT_REVIEWERS_REQUIRED"):
        verify_ai_goldset.verify(
            train_path=tmp_path / "train",
            holdout_path=tmp_path / "holdout",
            models=["same", "same"],
            base_url="http://127.0.0.1",
            output_path=tmp_path / "report.json",
        )

    monkeypatch.setattr(
        verify_ai_goldset,
        "_review",
        lambda _url, _model, cases: [
            {
                "id": item["id"],
                "verdict": item["expected_label"],
                "confidence": 1.0,
                "evidence_refs": list(item["evidence"]),
            }
            for item in cases
        ],
    )
    monkeypatch.setattr(verify_ai_goldset, "_digest", lambda _url, model: model + "-digest")
    report = verify_ai_goldset.verify(
        train_path=Path("evals/goldsets/judge-candidates-v1.jsonl"),
        holdout_path=Path("evals/hidden/judge-holdout-v1.jsonl"),
        models=["judge-a", "judge-b"],
        base_url="http://127.0.0.1",
        output_path=tmp_path / "report.json",
    )
    assert report["status"] == "ai_reviewed_candidate"
    assert report["human_gold_claimed"] is False
    assert report["train"]["case_count"] == 18 and report["holdout"]["case_count"] == 6
    assert json.loads((tmp_path / "report.json").read_text())["holdout"]["case_count"] == 6
