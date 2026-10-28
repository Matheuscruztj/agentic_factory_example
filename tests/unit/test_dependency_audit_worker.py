import json
from pathlib import Path

import pytest
from factory_workers.dependency_audit import DependencyAuditWorker

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "evals/fixtures/dependency-update"


def test_one_shot_worker_records_candidate_without_modifying_lockfiles(tmp_path):
    sources = [
        FIXTURES / "scenario.json",
        FIXTURES / "lock-before.json",
        FIXTURES / "lock-candidate.json",
    ]
    before = [path.read_bytes() for path in sources]
    output = tmp_path / "artifacts/audit.json"
    report = DependencyAuditWorker(tmp_path).run_once(
        evidence_path=sources[0],
        before_manifest=sources[1],
        candidate_manifest=sources[2],
        output_path=output,
    )

    assert report["status"] == "pending_approval"
    assert report["remediation_evidence"]["status"] == "pass"
    assert report["lockfiles_modified"] is False
    assert report["publication_authorized"] is False
    assert json.loads(output.read_text()) == report
    assert [path.read_bytes() for path in sources] == before


def test_one_shot_worker_refuses_output_outside_runtime_artifact_root(tmp_path):
    worker = DependencyAuditWorker(tmp_path / "allowed")
    with pytest.raises(ValueError, match="OUTPUT_OUTSIDE_ARTIFACT_ROOT"):
        worker.run_once(
            evidence_path=FIXTURES / "scenario.json",
            before_manifest=FIXTURES / "lock-before.json",
            candidate_manifest=FIXTURES / "lock-candidate.json",
            output_path=tmp_path / "escape.json",
        )
