from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def invoke(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_validate_checks_distinguishes_pass_fail_and_invalid(tmp_path: Path) -> None:
    passed = tmp_path / "pass.json"
    failed = tmp_path / "fail.json"
    invalid = tmp_path / "invalid.json"
    passed.write_text(json.dumps({"schema": 1, "check": "unit", "ok": 1}))
    failed.write_text(json.dumps({"schema": 1, "check": "lint", "ok": 0}))
    invalid.write_text("not-json")

    result = invoke("validate_checks.py", str(passed))
    assert result.returncode == 0
    assert json.loads(result.stdout)["status"] == "pass"

    result = invoke("validate_checks.py", str(failed))
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "fail"

    result = invoke("validate_checks.py", str(invalid))
    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "error"


def test_factory_boot_requires_operator_initialized_env() -> None:
    if (ROOT / ".env").exists():
        return
    result = invoke("local_boot.py", "--factory", "--api-only")
    assert result.returncode == 2
    assert json.loads(result.stdout)["reason"] == "LOCAL_ENV_NOT_INITIALIZED"
