from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_customer_registry_fixture_manifest_keeps_hidden_oracle_separate():
    fixture = json.loads((ROOT / "evals/fixtures/bug-cpf/case.json").read_text())
    manifest = json.loads((ROOT / "evals/fixtures/customer-registry-v1/manifest.json").read_text())
    issue_manifest = json.loads((ROOT / "evals/fixtures/issues-v1/manifest.json").read_text())
    hidden = ROOT / fixture["hidden_test_bundle"]
    assert fixture["id"] == "demo-cpf-checksum-v1"
    assert fixture["sandbox"]["network"] == "disabled"
    assert fixture["sandbox"]["secrets"] == "none"
    assert fixture["allowed_paths"]
    assert fixture["hidden_test_sha256"] == hashlib.sha256(hidden.read_bytes()).hexdigest()
    assert manifest["hidden_tests_are_not_executor_context"] is True
    assert manifest["sandbox"]["network"] == "disabled"
    assert issue_manifest["network"] == "disabled"
    assert all(issue["external_write"] is False for issue in issue_manifest["issues"])


def test_hidden_oracle_file_does_not_contain_fixture_examples_as_metadata():
    hidden = (ROOT / "evals/hidden/customer-registry-v1/bug-cpf.assertions.py").read_text()
    assert "CANARY" not in hidden
    assert "assert is_valid_cpf" in hidden
