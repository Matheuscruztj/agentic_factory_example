#!/usr/bin/env python3
"""Validate privacy labels, split separation, and frozen eval dataset hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = [
    Path("evals/fixtures/dev/cases.json"),
    Path("evals/fixtures/regression/cases.json"),
    Path("evals/fixtures/holdout/cases.json"),
    Path("evals/fixtures/context/regression-v1.json"),
]
MANIFEST = ROOT / "evals/dataset-manifest.json"
CALIBRATION_FILES = [
    Path("evals/fixtures/judge-calibration-v1.json"),
    Path("evals/rubrics/judge-v1.json"),
]


def dataset_hashes() -> dict[str, str]:
    files = [*DATASETS, *CALIBRATION_FILES]
    return {
        path.as_posix(): hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files
    }


def main() -> int:
    errors: list[str] = []
    seen: set[str] = set()
    case_count = 0
    provisional_labels = 0
    for path in DATASETS:
        try:
            value = json.loads((ROOT / path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"DATASET_INVALID:{path.as_posix()}")
            continue
        if (
            value.get("schema") != 1
            or path.parent.name != "context"
            and value.get("production_prompt_input") is not False
        ):
            errors.append(f"DATASET_METADATA_INVALID:{path.as_posix()}")
        for case in value.get("cases", []):
            case_id = case.get("id")
            if not isinstance(case_id, str) or case_id in seen:
                errors.append("CASE_ID_INVALID_OR_DUPLICATE")
            if isinstance(case_id, str):
                seen.add(case_id)
                case_count += 1
            if path.parent.name != "context":
                if not case.get("expected_verdict") or not isinstance(
                    case.get("deterministic_checks"), list
                ):
                    errors.append("CASE_ORACLE_REQUIRED")
                if case.get("expected_label") != case.get("expected_verdict"):
                    errors.append("EXPECTED_LABEL_MISMATCH")
                if case.get("label_source") != "human-reviewed":
                    provisional_labels += 1
    try:
        calibration = json.loads((ROOT / CALIBRATION_FILES[0]).read_text(encoding="utf-8"))
        if calibration.get("schema") != 1:
            errors.append("CALIBRATION_SCHEMA_INVALID")
        for case in calibration.get("cases", []):
            if case.get("gold") not in {"pass", "fail", "uncertain"} or not isinstance(
                case.get("evidence"), dict
            ):
                errors.append("CALIBRATION_CASE_INVALID")
        case_count += len(calibration.get("cases", []))
        if calibration.get("label_source") != "human-reviewed":
            provisional_labels += len(calibration.get("cases", []))
    except (OSError, json.JSONDecodeError):
        errors.append("CALIBRATION_DATASET_INVALID")
    hashes = dataset_hashes()
    try:
        frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if frozen.get("hashes") != hashes:
            errors.append("DATASET_HASH_MISMATCH")
    except (OSError, json.JSONDecodeError):
        errors.append("DATASET_MANIFEST_MISSING")
    result = {
        "schema": 1,
        "check": "eval-datasets",
        "status": "fail" if errors else "pass",
        "ok": int(not errors),
        "exit_code": int(bool(errors)),
        "metrics": {
            "datasets": len(DATASETS) + 1,
            "cases": case_count,
            "provisional_labels_pending_human_review": provisional_labels,
        },
        "artifact": "evals/dataset-manifest.json",
        "hashes": hashes,
        "errors": errors,
    }
    print(json.dumps(result, separators=(",", ":")))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
