from __future__ import annotations

import subprocess

from quality_gates.tool_adapter import run_quality_tool


def test_quality_tool_classifies_pass_fail_and_infrastructure(tmp_path, monkeypatch):
    monkeypatch.setattr("quality_gates.tool_adapter.shutil.which", lambda _name: "/tool")
    outcomes = iter([0, 1, 127])

    def run(*_args, **_kwargs):
        code = next(outcomes)
        return subprocess.CompletedProcess([], code, "ok", "")

    monkeypatch.setattr("quality_gates.tool_adapter.subprocess.run", run)
    passed = run_quality_tool(["pytest", "-q"], tool="pytest", artifact_dir=tmp_path)
    failed = run_quality_tool(["ruff", "check"], tool="ruff", artifact_dir=tmp_path)
    infra = run_quality_tool(["mypy", "."], tool="mypy", artifact_dir=tmp_path)
    assert (passed.status, passed.exit_code) == ("pass", 0)
    assert (failed.status, failed.exit_code, failed.error_class) == ("fail", 1, "code")
    assert (infra.status, infra.exit_code, infra.error_class) == ("error", 2, "infrastructure")
    assert passed.artifact_sha256 and failed.artifact_sha256 and infra.artifact_sha256


def test_optional_missing_scanner_is_skipped_and_secrets_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr("quality_gates.tool_adapter.shutil.which", lambda _name: None)
    skipped = run_quality_tool(
        ["semgrep", "scan"], tool="semgrep", artifact_dir=tmp_path, optional=True
    )
    assert skipped.status == "skipped" and skipped.exit_code == 0

    monkeypatch.setattr("quality_gates.tool_adapter.shutil.which", lambda _name: "/tool")
    monkeypatch.setattr(
        "quality_gates.tool_adapter.subprocess.run",
        lambda *_a, **_k: subprocess.CompletedProcess([], 0, "Bearer sk-secret api_key=canary", ""),
    )
    result = run_quality_tool(["ruff"], tool="ruff-safe", artifact_dir=tmp_path)
    content = (tmp_path / "ruff-safe.log").read_text()
    assert "sk-secret" not in content and "canary" not in content
    assert "[REDACTED]" in content
    assert result.status == "pass"
