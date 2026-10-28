#!/usr/bin/env python3
"""Fail-closed validation for the draft suite lifecycle catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_SUITES = {
    "grader_meta",
    "judge_calibration",
    "interaction",
    "capability",
    "regression",
    "harness_reliability",
    "tool_usability",
}
LIFECYCLE = {"candidate", "reviewed", "active", "quarantined", "retired"}


def validate_catalog(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict) or value.get("schema") != 1:
        return ["CATALOG_SCHEMA_INVALID"]
    rows = value.get("suites")
    if not isinstance(rows, list):
        return ["CATALOG_SUITES_INVALID"]
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("SUITE_ROW_INVALID")
            continue
        suite_id = row.get("id")
        if not isinstance(suite_id, str) or not suite_id or suite_id in seen:
            errors.append("SUITE_ID_INVALID_OR_DUPLICATE")
            continue
        seen.add(suite_id)
        if type(row.get("version")) is not int or row["version"] < 1:
            errors.append(f"SUITE_VERSION_INVALID:{suite_id}")
        for field in ("owner", "scope", "split_policy"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"SUITE_{field.upper()}_MISSING:{suite_id}")
    if seen != REQUIRED_SUITES:
        errors.append("SUITE_SET_MISMATCH")
    lifecycle = value.get("incident_lifecycle")
    if not isinstance(lifecycle, list) or set(lifecycle) != LIFECYCLE:
        errors.append("INCIDENT_LIFECYCLE_INVALID")
    if value.get("status") != "candidate_catalog_not_activated":
        errors.append("DRAFT_CATALOG_MUST_REMAIN_INACTIVE")
    if (
        value.get("holdout_claimed") is not False
        or value.get("production_prompt_input") is not False
    ):
        errors.append("DRAFT_DATA_CANNOT_CLAIM_HOLDOUT_OR_PRODUCTION")
    if (
        not isinstance(value.get("promotion_requires"), list)
        or len(value["promotion_requires"]) < 4
    ):
        errors.append("PROMOTION_CONTROLS_INCOMPLETE")
    return errors


def main() -> int:
    path = Path("evals/suite-catalog-v1.json")
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(json.dumps({"status": "fail", "errors": ["CATALOG_UNREADABLE"]}))
        return 1
    errors = validate_catalog(catalog)
    print(json.dumps({"status": "fail" if errors else "pass", "errors": errors}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
