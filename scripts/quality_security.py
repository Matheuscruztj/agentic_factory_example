#!/usr/bin/env python3
"""SAST (Bandit/Semgrep), dependency audits and secrets on sanitized source."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.quality_common import ROOT, QualityContext, print_result  # noqa: E402

SEMGREP_IMAGE = (
    "semgrep/semgrep@sha256:3db5c7af55eb1f512eac0abf0ab69a97b52c74b5e9a27314c221aee1a78d7ab2"
)
GITLEAKS_IMAGE = (
    "zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
)


def scanner_result(step: dict, output: str, kind: str) -> dict:
    """Tool-specific exits are not our contract: require a complete JSON report."""
    if step.get("error"):
        return step
    try:
        report = json.loads(output)
        if kind != "gitleaks" and not isinstance(report, dict):
            raise ValueError("SCANNER_REPORT_INVALID")
        if kind == "bandit":
            if not isinstance(report.get("results"), list) or report.get("errors"):
                raise ValueError("BANDIT_SCAN_INCOMPLETE")
            if not isinstance(report.get("metrics"), dict) or len(report["metrics"]) < 2:
                raise ValueError("BANDIT_NO_FILES_SCANNED")
            findings = report["results"]
            blocking = sum(x.get("issue_severity") == "HIGH" for x in findings)
            metrics = {
                "findings": len(findings),
                "high": blocking,
                "medium": sum(x.get("issue_severity") == "MEDIUM" for x in findings),
                "files": max(0, len(report.get("metrics", {})) - 1),
            }
        elif kind == "semgrep":
            if not isinstance(report.get("results"), list) or report.get("errors"):
                raise ValueError("SEMGREP_SCAN_INCOMPLETE")
            findings = report["results"]
            blocking = sum(x.get("extra", {}).get("severity") == "ERROR" for x in findings)
            scanned = report.get("paths", {}).get("scanned", [])
            if not scanned:
                raise ValueError("SEMGREP_NO_FILES_SCANNED")
            metrics = {"findings": len(findings), "high": blocking, "files": len(scanned)}
        elif kind == "pip-audit":
            if not isinstance(report.get("dependencies"), list) or not report["dependencies"]:
                raise ValueError("PIP_AUDIT_SCAN_INCOMPLETE")
            if any(x.get("skip_reason") for x in report["dependencies"]):
                raise ValueError("PIP_AUDIT_DEPENDENCIES_SKIPPED")
            blocking = sum(len(x.get("vulns", [])) for x in report["dependencies"])
            metrics = {
                "findings": blocking,
                "dependencies": len(report["dependencies"]),
                "severity_policy": "all_python_advisories_block_when_severity_unavailable",
            }
        elif kind == "pnpm":
            vulnerabilities = report["metadata"]["vulnerabilities"]
            if report["metadata"].get("totalDependencies", 0) <= 0 or any(
                type(vulnerabilities.get(key)) is not int or vulnerabilities[key] < 0
                for key in ("info", "low", "moderate", "high", "critical")
            ):
                raise ValueError("PNPM_AUDIT_SCAN_INCOMPLETE")
            blocking = int(vulnerabilities.get("high", 0)) + int(vulnerabilities.get("critical", 0))
            metrics = vulnerabilities
        else:
            if not isinstance(report, list):
                raise ValueError("GITLEAKS_REPORT_INVALID")
            blocking = len(report)
            metrics = {"findings": blocking}
        if step.get("tool_exit_code") not in (0, 1):
            raise ValueError("SCANNER_OPERATIONAL_FAILURE")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return {
            **step,
            "status": "error",
            "exit_code": 2,
            "error": str(exc) if str(exc).isupper() else "SCANNER_REPORT_INVALID",
        }
    return {
        **step,
        "status": "fail" if blocking else "pass",
        "exit_code": int(bool(blocking)),
        "metrics": metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.parse_args()
    ctx = QualityContext("quality-security")
    source = ctx.snapshot()
    steps = []

    def scan(name: str, command: list[str], cwd: Path, kind: str) -> None:
        step, output = ctx.execute(name, command, cwd=cwd, json_output=True)
        if kind == "gitleaks":
            try:
                output = (ctx.artifacts / "gitleaks-report.json").read_text()
                (ctx.artifacts / "gitleaks.json").write_text(output)
            except OSError:
                output = ""
        steps.append(scanner_result(step, output, kind))

    scan(
        "bandit",
        [
            sys.executable,
            "-m",
            "bandit",
            "-r",
            "apps",
            "packages",
            "workers",
            "scripts",
            "-f",
            "json",
            "-q",
            "--severity-level",
            "medium",
            "--confidence-level",
            "medium",
            "-x",
            "tests,apps/factory-api/tests,apps/customer-registry/api/tests",
        ],
        source,
        "bandit",
    )
    scan(
        "semgrep",
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=2g",
            "--cpus=2",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=512m",
            "-e",
            "HOME=/tmp/home",
            "-e",
            "XDG_CACHE_HOME=/tmp/cache",
            "-v",
            f"{source}:/src:ro",
            "-w",
            "/src",
            SEMGREP_IMAGE,
            "semgrep",
            "scan",
            "--config",
            "/src/infra/security/semgrep.yml",
            "--json",
            "--quiet",
            "--error",
            "--strict",
            "--metrics=off",
            "--disable-version-check",
            "--no-git-ignore",
            "--exclude",
            "**/tests/**",
            "apps",
            "packages",
            "workers",
            "scripts",
        ],
        source,
        "semgrep",
    )
    canary_command = [
        "docker",
        "run",
        "--rm",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=2g",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=512m",
        "-e",
        "HOME=/tmp/home",
        "-e",
        "XDG_CACHE_HOME=/tmp/cache",
        "-v",
        f"{source}:/src:ro",
        "-w",
        "/src",
        SEMGREP_IMAGE,
        "semgrep",
        "scan",
        "--config",
        "/src/infra/security/semgrep.yml",
        "--json",
        "--quiet",
        "--strict",
        "--error",
        "--metrics=off",
        "--disable-version-check",
        "infra/security/canaries",
    ]
    canary, output = ctx.execute("semgrep-canaries", canary_command, json_output=True)
    try:
        report = json.loads(output)
        expected = {
            "python-dynamic-code",
            "python-shell-true",
            "python-sql-fstring",
            "python-tls-disabled",
            "javascript-dynamic-code",
            "react-raw-html",
        }
        detected = {r["check_id"].split("factory.")[-1] for r in report["results"]}
        if (
            canary["tool_exit_code"] != 1
            or report.get("errors")
            or detected != expected
            or len(report["results"]) != 7
        ):
            raise ValueError("CANARY_RULE_COVERAGE_MISMATCH")
        canary.update(
            status="pass",
            exit_code=0,
            metrics={
                "rules_verified": len(detected),
                "expected_findings": 7,
                "benign_call_not_flagged": True,
            },
        )
    except (ValueError, KeyError, TypeError):
        canary.update(status="error", exit_code=2, error="SEMGREP_CANARY_VALIDATION_FAILED")
    steps.append(canary)
    requirements = ctx.artifacts / "python-requirements.txt"
    export, _ = ctx.execute(
        "uv-export",
        [
            "uv",
            "export",
            "--frozen",
            "--all-packages",
            "--all-groups",
            "--no-emit-workspace",
            "--no-hashes",
            "--format",
            "requirements-txt",
            "--output-file",
            str(requirements),
        ],
    )
    if export["exit_code"]:
        steps.append({**export, "status": "error", "exit_code": 2, "error": "UV_EXPORT_FAILED"})
    else:
        scan(
            "pip-audit",
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--progress-spinner",
                "off",
                "--format",
                "json",
                "-r",
                str(requirements),
            ],
            ROOT,
            "pip-audit",
        )
    for name, folder in (
        ("factory", "apps/factory-web"),
        ("registry", "apps/customer-registry/web"),
    ):
        scan(
            f"pnpm-audit-{name}",
            ["pnpm", "audit", "--json", "--audit-level", "high"],
            ROOT / folder,
            "pnpm",
        )
    scan(
        "gitleaks",
        [
            "docker",
            "run",
            "--rm",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "-v",
            f"{source}:/src:ro",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{ctx.artifacts}:/reports:rw",
            GITLEAKS_IMAGE,
            "dir",
            "--no-banner",
            "--redact=100",
            "--config",
            "/src/.gitleaks.toml",
            "--report-format",
            "json",
            "--report-path",
            "/reports/gitleaks-report.json",
            "/src",
        ],
        source,
        "gitleaks",
    )
    return print_result(
        ctx.finish(
            steps,
            scanners={"semgrep": SEMGREP_IMAGE, "gitleaks": GITLEAKS_IMAGE},
            scan_scope=(
                "Sanitized source; SAST excludes tests; Python and both pnpm lockfiles audited."
            ),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
