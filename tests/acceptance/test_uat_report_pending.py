from scripts.acceptance_report import _verify_approval, build_report


def test_uat_report_requires_a_valid_ai_acceptance_receipt(tmp_path):
    backlog = tmp_path / "backlog.json"
    backlog.write_text('{"tasks":[{"id":"FAC-093","status":"in_progress"}]}')
    unsigned = tmp_path / "unsigned.json"
    unsigned.write_text('{"reviewer":"agent","decision":"approve"}')

    report = build_report(backlog, unsigned)
    assert report["status"] == "pending_ai_acceptance"
    assert report["ai_reviewer"] is None
    assert "no AI acceptance is claimed" in report["acceptance_claim"]


def test_uat_signature_rejects_untrusted_identity_and_missing_manifest(tmp_path):
    root = tmp_path
    uat = root / ".runtime/artifacts/uat"
    uat.mkdir(parents=True)
    approval = {
        "reviewer_id": "invented-reviewer",
        "signed_at": "2026-01-01T00:00:00+00:00",
        "decision": "approve",
        "scope": "all-required-activities",
        "signature_file": ".runtime/artifacts/uat/signature",
        "evidence_manifest": ".runtime/artifacts/uat/manifest.json",
        "evidence_manifest_sha256": "0" * 64,
    }
    assert _verify_approval(approval, "a" * 64, root) is False
