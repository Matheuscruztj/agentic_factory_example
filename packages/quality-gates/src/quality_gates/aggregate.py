"""Deterministic aggregation of required local quality contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from quality_gates.schema import validate_result

DEFAULT_REQUIRED = (
    "quality-python",
    "quality-frontend",
    "quality-e2e",
    "quality-security",
    "quality-dast",
)


def aggregate_results(
    paths: list[str | Path],
    *,
    required: tuple[str, ...] = DEFAULT_REQUIRED,
    run_id: str | None = None,
) -> dict[str, Any]:
    by_check: dict[str, dict[str, Any]] = {}
    malformed: list[str] = []
    identity = None
    expected = None
    root = Path(__file__).resolve().parents[4]
    if run_id is not None:
        try:
            manifest = json.loads(
                (root / ".runtime/quality/runs" / run_id / "source-manifest.json").read_text()
            )
            expected = (run_id, manifest["git_sha"], manifest["source_sha256"])
        except (OSError, ValueError, KeyError):
            malformed.append("RUN_MANIFEST_MISSING_OR_INVALID")
    for raw_path in paths:
        path = Path(raw_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            malformed.append(path.name)
            continue
        if not isinstance(payload, dict) or validate_result(payload):
            malformed.append(path.name)
            continue
        if payload["check"] in by_check:
            malformed.append(path.name + ":DUPLICATE_CHECK")
            continue
        if run_id is not None:
            signature = (
                payload.get("run_id"),
                payload.get("git_sha"),
                payload.get("source_sha256"),
            )
            root = Path(__file__).resolve().parents[4]
            hashes = payload.get("artifacts_sha256")
            invalid = (
                signature != expected
                or not all(signature)
                or (identity is not None and signature != identity)
                or not isinstance(hashes, dict)
                or not hashes
                or not payload.get("steps")
            )
            if not invalid and isinstance(hashes, dict):
                for raw, digest in hashes.items():
                    artifact_path = root / raw
                    if (
                        not artifact_path.resolve().is_relative_to(
                            root / ".runtime/quality/runs" / run_id
                        )
                        or artifact_path.is_symlink()
                        or not artifact_path.is_file()
                        or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != digest
                    ):
                        invalid = True
                        break
            if invalid:
                malformed.append(path.name + ":PROVENANCE_OR_ARTIFACT_INVALID")
                continue
            identity = signature
        by_check[str(payload["check"])] = {"path": str(path), "result": payload}

    missing = sorted(set(required) - by_check.keys())
    failures: list[dict[str, str]] = []
    for check in required:
        entry = by_check.get(check)
        if not entry:
            continue
        result = entry["result"]
        if result["status"] != "pass":
            failures.append({"check": check, "status": result["status"], "artifact": entry["path"]})
        for step in result.get("steps", []):
            if not isinstance(step, dict):
                failures.append({"check": check, "status": "error", "artifact": entry["path"]})
                continue
            if step.get("status") not in {"pass", "fail", "error"}:
                failures.append({"check": check, "status": "error", "artifact": entry["path"]})
            if step.get("status") in {"fail", "error"}:
                failures.append(
                    {
                        "check": check,
                        "status": step["status"],
                        "artifact": str(step.get("artifact", entry["path"])),
                    }
                )

    code = (
        2
        if malformed or missing or any(x["status"] == "error" for x in failures)
        else (1 if failures else 0)
    )
    first_failure = failures[0] if failures else None
    return {
        "schema": 1,
        "check": "quality-aggregate",
        "status": {0: "pass", 1: "fail", 2: "error"}[code],
        "ok": int(code == 0),
        "exit_code": code,
        "run_id": run_id,
        "metrics": {
            "required": len(required),
            "present": len(required) - len(missing),
            "passed": sum(
                by_check.get(k, {}).get("result", {}).get("status") == "pass" for k in required
            ),
            "failed": len([x for x in failures if x["status"] == "fail"]),
            "errors": len(malformed)
            + len(missing)
            + len([x for x in failures if x["status"] == "error"]),
        },
        "first_failure": first_failure,
        "missing": missing,
        "malformed": malformed,
        "artifact": str(root / ".runtime/quality/runs" / run_id / "aggregate.json")
        if run_id
        else None,
        "artifacts": {key: value["path"] for key, value in by_check.items() if key in required},
        "errors": ["REQUIRED_GATE_MISSING_OR_INVALID"] if code == 2 else [],
    }
