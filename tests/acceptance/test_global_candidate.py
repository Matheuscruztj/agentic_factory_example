"""Receipt protocol tests use sealed synthetic records only, never live acceptance."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from scripts.acceptance_report import build_report
from scripts.ai_acceptance import get_or_create_receipt_key, seal_receipt
from scripts.global_acceptance import prepare_candidate, publish_candidate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def packet(tmp_path):
    root = tmp_path
    (root / "specs").mkdir()
    official = root / "specs/implementation-backlog.json"
    official.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "FAC-001",
                        "status": "done",
                        "acceptance": "proof",
                        "remaining_work": [],
                    },
                    {
                        "id": "FAC-139",
                        "status": "in_progress",
                        "acceptance": "global proof",
                        "remaining_work": ["final review"],
                    },
                ]
            }
        )
    )
    folder = root / ".runtime/artifacts/uat"
    folder.mkdir(parents=True)
    candidate = folder / "candidate.json"
    prepare_candidate(root, candidate)
    artifact = folder / "proof.json"
    artifact.write_text('{"status":"pass","synthetic_test_only":true}')
    ref = artifact.relative_to(root).as_posix()
    manifest = folder / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "scope": "all-required-activities",
                "backlog_sha256": sha(candidate),
                "required_activity_ids": ["FAC-001", "FAC-139"],
                "activities": [
                    {"id": k, "status": "done", "evidence_refs": [ref]}
                    for k in ["FAC-001", "FAC-139"]
                ],
                "artifacts": [{"path": ref, "sha256": sha(artifact)}],
                "gates": [{"status": "pass", "artifact": ref}],
            }
        )
    )
    prompt, response = folder / "prompt.json", folder / "response.json"
    prompt.write_text("synthetic protocol test only")
    response.write_text(
        json.dumps(
            {
                "decision": "approve",
                "verdict": "pass",
                "confidence": 0.9,
                "reviewer_model": "test-reviewer",
            }
        )
    )

    def seal():
        unsigned = {
            "reviewer_type": "local_ollama",
            "reviewer_model": "test-reviewer",
            "reviewer_digest": "a" * 64,
            "executor_model": "test-coder",
            "reviewed_at": datetime.now(UTC).isoformat(),
            "decision": "approve",
            "verdict": "pass",
            "confidence": 0.9,
            "scope": "all-required-activities",
            "prompt": prompt.relative_to(root).as_posix(),
            "prompt_sha256": sha(prompt),
            "response": response.relative_to(root).as_posix(),
            "response_sha256": sha(response),
            "evidence_manifest": manifest.relative_to(root).as_posix(),
            "evidence_manifest_sha256": sha(manifest),
            "backlog_sha256": sha(candidate),
            "evidence_refs": [ref],
            "previous_backlog_sha256": sha(official),
        }
        receipt = folder / "receipt.json"
        receipt.write_text(json.dumps(seal_receipt(unsigned, get_or_create_receipt_key(root))))
        return receipt

    yield root, official, candidate, manifest, artifact, seal


def test_candidate_is_not_official_before_verified_acceptance(packet):
    root, official, candidate, manifest, artifact, seal = packet
    assert json.loads(official.read_text())["tasks"][1]["status"] == "in_progress"
    assert json.loads(candidate.read_text())["tasks"][1]["status"] == "done"
    receipt = seal()
    assert build_report(official, receipt, root)["status"] == "pending_ai_acceptance"
    assert build_report(candidate, receipt, root)["status"] == "accepted_by_ai"


def test_atomic_publish_and_recovery_are_idempotent(packet):
    root, official, candidate, manifest, artifact, seal = packet
    receipt = seal()
    assert publish_candidate(root, candidate, receipt)["status"] == "accepted_by_ai"
    assert official.read_bytes() == candidate.read_bytes()
    assert publish_candidate(root, candidate, receipt)["status"] == "accepted_by_ai"


def test_reduced_manifest_cannot_hide_a_required_activity(packet):
    root, official, candidate, manifest, artifact, seal = packet
    body = json.loads(manifest.read_text())
    body["required_activity_ids"] = ["FAC-139"]
    body["activities"] = body["activities"][1:]
    manifest.write_text(json.dumps(body))
    assert build_report(candidate, seal(), root)["status"] == "pending_ai_acceptance"


def test_official_change_after_review_blocks_publication(packet):
    root, official, candidate, manifest, artifact, seal = packet
    receipt = seal()
    original = official.read_bytes()
    official.write_bytes(original + b"\n")
    with pytest.raises(ValueError, match="OFFICIAL_BACKLOG_CHANGED"):
        publish_candidate(root, candidate, receipt)
    assert official.read_bytes() == original + b"\n"


def test_artifact_tampering_blocks_publication(packet):
    root, official, candidate, manifest, artifact, seal = packet
    receipt = seal()
    artifact.write_text('{"status":"fail"}')
    with pytest.raises(ValueError, match="VERIFICATION_FAILED"):
        publish_candidate(root, candidate, receipt)
    assert json.loads(official.read_text())["tasks"][1]["status"] == "in_progress"


def test_preparation_does_not_erase_other_pending_work(tmp_path):
    (tmp_path / "specs").mkdir()
    path = tmp_path / "specs/implementation-backlog.json"
    path.write_text(
        json.dumps(
            {
                "tasks": [
                    {"id": "FAC-001", "status": "in_progress"},
                    {"id": "FAC-139", "status": "in_progress"},
                ]
            }
        )
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="REQUIRED_ACTIVITIES_OPEN"):
        prepare_candidate(tmp_path, tmp_path / ".runtime/candidate.json")
    assert path.read_bytes() == before


def test_candidate_cannot_rewrite_a_completed_activity_or_erase_scope(packet):
    from scripts.global_acceptance import validate_candidate

    root, official, candidate, manifest, artifact, seal = packet
    body = json.loads(candidate.read_text())
    body["tasks"][0]["acceptance"] = "An easier invented criterion"
    candidate.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="CHANGED_SCOPE_OR_EVIDENCE"):
        validate_candidate(root, candidate)
