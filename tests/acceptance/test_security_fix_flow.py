import json
from pathlib import Path

from scripts.propose_dependency_upgrade import evaluate_remediation, propose


def test_vulnerability_evidence_creates_review_only_upgrade_without_publication(tmp_path):
    source = Path("evals/fixtures/dependency-update/scenario.json")
    before = source.read_bytes()
    proposal = propose(source)
    artifact = tmp_path / "proposal.json"
    artifact.write_text(json.dumps(proposal), encoding="utf-8")

    assert proposal["from_version"] == "1.4.0"
    assert proposal["to_version"] == "1.4.2"
    assert proposal["lockfile_changed"] is False
    assert proposal["approved"] is False
    assert proposal["publication_approval_required"] is True
    assert source.read_bytes() == before
    assert json.loads(artifact.read_text())["status"] == "pending_human_review"


def test_dependency_fixture_proves_finding_before_and_clear_candidate_after():
    root = Path("evals/fixtures/dependency-update")
    report = evaluate_remediation(
        root / "scenario.json",
        root / "lock-before.json",
        root / "lock-candidate.json",
    )

    assert report["status"] == "pass"
    assert report["before"] == {"version": "1.4.0", "finding": "high"}
    assert report["candidate"] == {"version": "1.4.2", "finding": None}
    assert report["candidate_is_fixture_only"] is True
    assert report["workspace_lockfile_changed"] is False
    assert report["publication_approval_required"] is True
    assert report["publication_authorized"] is False
    assert len(report["evidence_sha256"]) == 3


def test_dependency_fixture_rejects_candidate_that_does_not_reach_fixed_version(tmp_path):
    root = Path("evals/fixtures/dependency-update")
    candidate = tmp_path / "lock.json"
    candidate.write_text('{"dependencies":{"demo-parser":"1.4.1"}}', encoding="utf-8")

    try:
        evaluate_remediation(root / "scenario.json", root / "lock-before.json", candidate)
    except ValueError as exc:
        assert str(exc) == "DEPENDENCY_REMEDIATION_INSUFFICIENT"
    else:
        raise AssertionError("unsafe candidate version was accepted")
