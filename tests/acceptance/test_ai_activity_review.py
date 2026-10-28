from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from eval_engine.judge import AcceptanceVerdict, build_acceptance_prompt

from scripts import ai_acceptance


def test_ai_activity_review_binds_verdict_to_hashes_and_local_key(tmp_path, monkeypatch) -> None:
    root = tmp_path
    (root / "specs").mkdir()
    backlog = {
        "schema_version": 1,
        "tasks": [
            {
                "id": "FAC-999",
                "title": "Synthetic component",
                "status": "in_progress",
                "acceptance": "The component meets its criterion.",
                "paths": "packages/example.py",
                "depends_on": [],
                "risk": "low",
            }
        ],
    }
    backlog_bytes = json.dumps(backlog, separators=(",", ":")).encode()
    (root / "specs/implementation-backlog.json").write_bytes(backlog_bytes)
    source = root / ".runtime/artifacts/ai-acceptance/FAC-999/source.txt"
    source.parent.mkdir(parents=True)
    source.write_text("component code and passing test result", encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        "schema": 1,
        "scope": "activity",
        "activity_id": "FAC-999",
        "backlog_sha256": hashlib.sha256(backlog_bytes).hexdigest(),
        "implementation_summary": "Implemented the synthetic component and verified its behavior.",
        "artifacts": [{"path": source.relative_to(root).as_posix(), "sha256": source_hash}],
        "gates": [
            {
                "activity_id": "FAC-999",
                "name": "synthetic-test",
                "status": "pass",
                "artifact": source.relative_to(root).as_posix(),
                "artifact_sha256": source_hash,
            }
        ],
    }
    manifest_path = root / ".runtime/artifacts/ai-acceptance/FAC-999/manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def prompt_values(**kwargs):
        evidence = {
            source.relative_to(root).as_posix(): (
                f"sha256={source_hash}\ncomponent code and passing test result"
            ),
            "gate:1": json.dumps(manifest["gates"][0], ensure_ascii=False, sort_keys=True),
        }
        return build_acceptance_prompt(**{**kwargs, "evidence": evidence})

    response = json.dumps(
        {
            "schema": 1,
            "judge_model": "reviewer-model",
            "executor_model": "executor-model",
            "confidence": 0.95,
            "verdict": "pass",
            "rationale": "The cited test evidence supports the acceptance criterion.",
            "evidence_refs": [source.relative_to(root).as_posix(), "gate:1"],
            "human_review_required": False,
        }
    )
    prompt = prompt_values(
        executor_model="executor-model",
        answer=json.dumps(
            {
                "activity": {
                    key: backlog["tasks"][0].get(key)
                    for key in ("id", "title", "acceptance", "paths", "depends_on", "risk")
                },
                "implementation_summary": manifest["implementation_summary"],
                "required_checks": ["synthetic-test"],
                "claim": "The component meets its recorded acceptance criteria.",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        rubric={
            "decision_order": [
                "Any failed/missing gate or hash mismatch means fail or uncertain.",
                "Approve only when every criterion is directly supported by cited evidence.",
                "Do not treat a related downstream integration as proof of this component.",
                "Reject claims unsupported by the cited files or test output.",
            ],
            "minimum_confidence_for_approval": 0.8,
        },
    )

    class FakeJudge:
        def __init__(self, *, base_url, model):
            assert model == "reviewer-model"

        def accept(self, *, executor_model, answer, evidence, rubric):
            return AcceptanceVerdict(
                1,
                "reviewer-model",
                executor_model,
                0.95,
                "pass",
                "The cited test evidence supports the acceptance criterion.",
                (source.relative_to(root).as_posix(), "gate:1"),
                False,
                hashlib.sha256(prompt.encode()).hexdigest(),
                hashlib.sha256(response.encode()).hexdigest(),
                response,
            )

    monkeypatch.setattr(ai_acceptance, "OllamaJudge", FakeJudge)
    monkeypatch.setattr(ai_acceptance, "_model_digest", lambda *_args: "a" * 64)
    receipt = ai_acceptance.review_activity(
        activity_id="FAC-999",
        manifest_path=manifest_path,
        root=root,
        judge_model="reviewer-model",
        executor_model="executor-model",
    )

    key = (root / ".runtime/artifacts/uat/ai-acceptance.key").read_bytes()
    assert receipt["decision"] == "approve"
    assert receipt["score"] is None
    assert receipt["review_protocol"] == "binary_activity_acceptance_v1"
    assert ai_acceptance.verify_receipt_hmac(receipt, key)
    assert Path(root / receipt["response"]).read_text() == response


def test_ai_activity_review_refuses_open_dependencies(tmp_path):
    root = tmp_path
    (root / "specs").mkdir()
    backlog = {
        "schema_version": 1,
        "tasks": [
            {
                "id": "FAC-999",
                "title": "Synthetic component",
                "status": "in_progress",
                "acceptance": "The component meets its criterion.",
                "depends_on": ["FAC-998"],
            }
        ],
    }
    (root / "specs/implementation-backlog.json").write_text(json.dumps(backlog))
    with pytest.raises(ValueError, match="AI_ACTIVITY_DEPENDENCIES_OPEN"):
        ai_acceptance.review_activity(
            activity_id="FAC-999",
            manifest_path=root / ".runtime/unused.json",
            root=root,
            judge_model="reviewer-model",
            executor_model="executor-model",
        )
