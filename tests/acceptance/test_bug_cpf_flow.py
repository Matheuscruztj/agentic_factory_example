import json
import shutil
import subprocess
import sys
from pathlib import Path

from customer_registry.models import User
from customer_registry.services.cpf import is_valid_cpf


def _old_format_only_check(value: str) -> bool:
    return value.isdigit() and len(value) == 11


def test_bug_cpf_reproduction_and_checksum_fix_are_scoped_to_synthetic_fixture():
    fixture_path = Path("evals/fixtures/bug-cpf/case.json")
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    valid = fixture["valid_synthetic_example"]
    invalid = fixture["invalid_synthetic_example"]

    # Reproduce the old bug: length/format-only code considers the bad checksum acceptable.
    assert _old_format_only_check(invalid) is True
    assert is_valid_cpf(valid) is True
    assert is_valid_cpf(invalid) is False
    assert fixture["not_persisted"] is True
    assert fixture["production_personal_data"] is False
    assert not hasattr(User, "cpf")
    assert list(Path("apps/customer-registry/api/src/customer_registry").rglob("*.py"))


def test_canonical_baseline_fixture_reproduces_the_failure(tmp_path):
    baseline = Path("evals/fixtures/bug-cpf/baseline").resolve()
    working_copy = tmp_path / "baseline"
    shutil.copytree(baseline, working_copy)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "test_cpf.py"],
        cwd=working_copy,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "test_invalid_synthetic_check_digit_is_rejected" in output
    assert "1 failed" in output
