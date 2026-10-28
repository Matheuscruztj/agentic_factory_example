"""Canonical, secret-safe result shape for local validation commands."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

STATUSES = {"pass", "fail", "error", "not_implemented"}


def validate_result(result: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"schema", "check", "status", "ok", "exit_code", "metrics", "artifact", "errors"}
    errors.extend(f"FIELD_REQUIRED_{name.upper()}" for name in sorted(required - result.keys()))
    if result.get("schema") != 1:
        errors.append("SCHEMA_VERSION_INVALID")
    if not isinstance(result.get("check"), str) or not result["check"].strip():
        errors.append("CHECK_REQUIRED")
    if result.get("status") not in STATUSES:
        errors.append("STATUS_INVALID")
    code = result.get("exit_code")
    if type(code) is not int or code not in (0, 1, 2):
        errors.append("EXIT_CODE_INVALID")
    if result.get("status") == "pass" and code != 0:
        errors.append("PASS_EXIT_CODE_MISMATCH")
    if result.get("status") == "fail" and code != 1:
        errors.append("FAIL_EXIT_CODE_MISMATCH")
    if result.get("status") == "error" and code != 2:
        errors.append("ERROR_EXIT_CODE_MISMATCH")
    if type(result.get("ok")) is not int or result.get("ok") not in (0, 1):
        errors.append("OK_INVALID")
    elif result.get("ok") != int(result.get("status") == "pass"):
        errors.append("OK_STATUS_MISMATCH")
    metrics = result.get("metrics", {})
    if not isinstance(metrics, Mapping):
        errors.append("METRICS_INVALID")
    artifact = result.get("artifact")
    if artifact is not None and not isinstance(artifact, (str, list, Mapping)):
        errors.append("ARTIFACT_INVALID")
    details = result.get("errors", [])
    if not isinstance(details, list) or any(not isinstance(item, str) for item in details):
        errors.append("ERRORS_INVALID")
    return errors


def result_status(exit_code: int) -> str:
    if exit_code not in (0, 1, 2):
        raise ValueError("EXIT_CODE_MUST_BE_0_1_OR_2")
    return {0: "pass", 1: "fail", 2: "error"}[exit_code]
