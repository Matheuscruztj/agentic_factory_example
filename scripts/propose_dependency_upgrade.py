#!/usr/bin/env python3
"""Turn scanner evidence into a review-only upgrade proposal, never mutate locks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def propose(path: Path) -> dict:
    raw = path.read_bytes()
    scenario = json.loads(raw)
    required = ("package", "current_version", "fixed_version", "advisory", "severity")
    if any(not isinstance(scenario.get(key), str) or not scenario[key] for key in required):
        raise ValueError("DEPENDENCY_EVIDENCE_INVALID")
    if scenario["severity"] not in {"high", "critical"}:
        raise ValueError("DEPENDENCY_SEVERITY_NOT_ACTIONABLE")
    if scenario["current_version"] == scenario["fixed_version"]:
        raise ValueError("DEPENDENCY_ALREADY_FIXED")
    return {
        "schema": 1,
        "kind": "dependency-upgrade-proposal",
        "package": scenario["package"],
        "from_version": scenario["current_version"],
        "to_version": scenario["fixed_version"],
        "advisory": scenario["advisory"],
        "severity": scenario["severity"],
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "lockfile_changed": False,
        "publication_approval_required": True,
        "approved": False,
        "status": "pending_human_review",
    }


def _version(value: object) -> tuple[int, ...]:
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+){1,3}", value):
        raise ValueError("DEPENDENCY_VERSION_INVALID")
    return tuple(int(part) for part in value.split("."))


def evaluate_remediation(scenario_path: Path, before_path: Path, candidate_path: Path) -> dict:
    """Compare a vulnerable fixture manifest with a proposed, un-applied manifest."""
    scenario_raw = scenario_path.read_bytes()
    scenario = json.loads(scenario_raw)
    before_raw = before_path.read_bytes()
    candidate_raw = candidate_path.read_bytes()
    before = json.loads(before_raw)
    candidate = json.loads(candidate_raw)
    package = scenario.get("package")
    required = ("current_version", "fixed_version", "advisory", "severity")
    if not isinstance(package, str) or not package or any(
        not isinstance(scenario.get(key), str) or not scenario[key] for key in required
    ):
        raise ValueError("DEPENDENCY_EVIDENCE_INVALID")
    if scenario.get("synthetic_advisory") is not True:
        raise ValueError("DEPENDENCY_FIXTURE_MUST_BE_SYNTHETIC")
    for manifest in (before, candidate):
        if not isinstance(manifest, dict) or not isinstance(manifest.get("dependencies"), dict):
            raise ValueError("DEPENDENCY_MANIFEST_INVALID")
        if package not in manifest["dependencies"]:
            raise ValueError("DEPENDENCY_NOT_IN_MANIFEST")
    before_version = before["dependencies"][package]
    candidate_version = candidate["dependencies"][package]
    if before_version != scenario["current_version"]:
        raise ValueError("DEPENDENCY_BASELINE_MISMATCH")
    fixed = _version(scenario["fixed_version"])
    if _version(before_version) >= fixed:
        raise ValueError("DEPENDENCY_BASELINE_NOT_VULNERABLE")
    if _version(candidate_version) < fixed:
        raise ValueError("DEPENDENCY_REMEDIATION_INSUFFICIENT")
    return {
        "schema": 1,
        "status": "pass",
        "advisory": scenario["advisory"],
        "package": package,
        "before": {"version": before_version, "finding": scenario["severity"]},
        "candidate": {"version": candidate_version, "finding": None},
        "evidence_sha256": {
            "scenario": hashlib.sha256(scenario_raw).hexdigest(),
            "baseline_manifest": hashlib.sha256(before_raw).hexdigest(),
            "candidate_manifest": hashlib.sha256(candidate_raw).hexdigest(),
        },
        "candidate_is_fixture_only": True,
        "workspace_lockfile_changed": False,
        "publication_approval_required": True,
        "publication_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--before-manifest", type=Path)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path(".runtime/dependency-upgrade-proposal.json")
    )
    args = parser.parse_args()
    result = propose(args.evidence)
    if args.before_manifest or args.candidate_manifest:
        if not args.before_manifest or not args.candidate_manifest:
            parser.error("--before-manifest and --candidate-manifest must be supplied together")
        result["remediation_evidence"] = evaluate_remediation(
            args.evidence, args.before_manifest, args.candidate_manifest
        )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
