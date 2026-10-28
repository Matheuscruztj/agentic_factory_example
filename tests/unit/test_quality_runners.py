import hashlib
import json
import subprocess
from types import SimpleNamespace

import pytest
from quality_gates.aggregate import aggregate_results
from quality_gates.schema import validate_result

from scripts.quality_common import ROOT, QualityContext, safe_source
from scripts.quality_dast import zap_result
from scripts.quality_security import scanner_result


@pytest.mark.parametrize("code", [0, 2])
def test_zap_warning_exit_is_not_infrastructure_failure(code):
    result = zap_result({"tool_exit_code": code}, {"site": [{"alerts": [{"riskcode": "2"}]}]})
    assert result["status"] == "pass"
    assert result["metrics"]["medium"] == 1


def test_zap_high_alert_blocks_even_when_tool_returns_zero():
    result = zap_result({"tool_exit_code": 0}, {"site": [{"alerts": [{"riskcode": "3"}]}]})
    assert result["exit_code"] == 1


@pytest.mark.parametrize(
    "code,report", [(3, {"site": [{"alerts": []}]}), (0, {}), (0, {"site": []})]
)
def test_zap_missing_or_operational_failure_is_error(code, report):
    assert zap_result({"tool_exit_code": code}, report)["exit_code"] == 2


@pytest.mark.parametrize("kind", ["bandit", "semgrep", "pip-audit", "pnpm", "gitleaks"])
@pytest.mark.parametrize("report", ["{}", "null"])
def test_scanner_invalid_report_is_error(kind, report):
    assert scanner_result({"tool_exit_code": 0}, report, kind)["exit_code"] == 2


def test_semgrep_high_finding_blocks():
    report = {
        "results": [{"extra": {"severity": "ERROR"}}],
        "errors": [],
        "paths": {"scanned": ["app.py"]},
    }
    assert scanner_result({"tool_exit_code": 1}, json.dumps(report), "semgrep")["exit_code"] == 1


@pytest.mark.parametrize(
    "path",
    [
        "apps/demo/.env",
        "nested/.aws/config",
        "x/private.key",
        "../outside",
        ".runtime/operator-password.txt",
    ],
)
def test_snapshot_rejects_nested_secrets(path):
    assert not safe_source(path)


def test_existing_snapshot_refreshes_late_coverage_reports(tmp_path, monkeypatch):
    import scripts.quality_common as quality_common

    monkeypatch.setattr(quality_common, "ROOT", tmp_path)
    run_dir = tmp_path / "run"
    source = run_dir / "source"
    source.mkdir(parents=True)
    report = run_dir / "python/coverage.xml"
    report.parent.mkdir()
    report.write_text(
        f"<coverage><source>{tmp_path}</source></coverage>", encoding="utf-8"
    )

    context = object.__new__(QualityContext)
    context.run_dir = run_dir
    context.manifest = {"files_sha256": {}}

    assert context.snapshot() == source
    copied = source / "sonar-reports/python-coverage.xml"
    assert copied.read_text(encoding="utf-8") == "<coverage><source>/usr/src</source></coverage>"


def test_legacy_minimal_contract_rejected(tmp_path):
    from tests.unit.test_script_contracts import invoke

    path = tmp_path / "legacy.json"
    path.write_text('{"schema":1,"ok":1}')
    assert invoke("validate_checks.py", str(path)).returncode == 2


def test_aggregate_rejects_stale_identity_and_tampered_artifacts(tmp_path):
    run_id = "unit-provenance"
    directory = ROOT / ".runtime/quality/runs" / run_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "source-manifest.json").write_text(
        json.dumps({"git_sha": "abc", "source_sha256": "123"})
    )
    log = directory / "check.log"
    log.write_text("passed")
    report = tmp_path / "python.json"
    payload = {
        "schema": 1,
        "check": "quality-python",
        "status": "pass",
        "ok": 1,
        "exit_code": 0,
        "metrics": {},
        "artifact": str(log),
        "errors": [],
        "steps": [{"name": "pytest", "status": "pass"}],
        "run_id": run_id,
        "git_sha": "abc",
        "source_sha256": "123",
        "artifacts_sha256": {
            str(log.relative_to(ROOT)): hashlib.sha256(log.read_bytes()).hexdigest()
        },
    }
    report.write_text(json.dumps(payload))
    good = aggregate_results([report], required=("quality-python",), run_id=run_id)
    assert good["ok"] == 1
    assert not validate_result(good)
    assert (
        aggregate_results([report], required=("quality-python",), run_id="other")["exit_code"] == 2
    )
    assert (
        aggregate_results([report, report], required=("quality-python",), run_id=run_id)[
            "exit_code"
        ]
        == 2
    )
    log.write_text("changed")
    assert (
        aggregate_results([report], required=("quality-python",), run_id=run_id)["exit_code"] == 2
    )


@pytest.mark.parametrize(
    "kind,report",
    [
        ("bandit", {"results": [], "metrics": {"_totals": {}}}),
        ("pip-audit", {"dependencies": []}),
        ("pnpm", {"metadata": {"vulnerabilities": {}}}),
    ],
)
def test_empty_security_scan_cannot_pass(kind, report):
    result = scanner_result({"tool_exit_code": 0}, json.dumps(report), kind)
    assert result["exit_code"] == 2


@pytest.mark.parametrize(
    "error",
    [subprocess.CalledProcessError(1, ["docker"]), subprocess.TimeoutExpired(["docker"], 15)],
)
def test_docker_inspect_failure_is_infrastructure_error(monkeypatch, error):
    import scripts.quality_stack as stack

    monkeypatch.setenv("FACTORY_QUALITY_RUN_ID", "test-run")
    monkeypatch.setattr(
        stack,
        "QualityContext",
        lambda *a, **kw: SimpleNamespace(run_id="test-run", manifest={"source_sha256": "abc"}),
    )
    monkeypatch.setattr(stack, "source_manifest", lambda: {"source_sha256": "abc"})

    def broken(*args, **kwargs):
        raise error

    monkeypatch.setattr(stack.subprocess, "run", broken)
    with pytest.raises(RuntimeError, match="RUNNING_QUALITY_TARGET_UNAVAILABLE"):
        stack.active_context("quality-e2e")
