from __future__ import annotations

from dataclasses import dataclass

from eval_engine.judge import JudgeError

from scripts import evaluate_ai_judge


@dataclass
class Verdict:
    verdict: str = "uncertain"
    confidence: float = 0.9
    evidence_refs: tuple[str, ...] = ()
    human_review_required: bool = True
    prompt_sha256: str = "a" * 64
    response_sha256: str = "b" * 64


def test_judge_counts_invalid_json_and_never_emits_numeric_score(monkeypatch):
    class FakeJudge:
        def __init__(self, **_kwargs):
            self.calls = 0

        def accept(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise JudgeError("JUDGE_RESPONSE_INVALID")
            return Verdict()

    monkeypatch.setattr(evaluate_ai_judge, "OllamaJudge", FakeJudge)
    report = evaluate_ai_judge.evaluate(
        cases=[
            {"id": "bad-json", "answer": "claim", "evidence": {}},
            {"id": "missing-evidence", "answer": "claim", "evidence": {}},
        ],
        judge_model="judge",
        executor_model="executor",
    )
    assert report["counts"]["invalid_json"] == 1
    assert report["counts"]["reviewed"] == 1
    assert report["results"][0]["error_class"] == "invalid_json"
    assert "score" not in report["results"][1]
    assert report["results"][1]["verdict"] == "uncertain"
    assert report["status"] == "incomplete"
