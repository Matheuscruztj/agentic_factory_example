#!/usr/bin/env python3
"""Validate compact JSON quality-check artifacts and emit one summary line."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print(
            json.dumps(
                {
                    "schema": 1,
                    "check": "validate-checks",
                    "status": "error",
                    "ok": 0,
                    "reason": "ARTIFACTS_REQUIRED",
                },
                separators=(",", ":"),
            )
        )
        return 2
    outcomes = []
    for raw in sys.argv[1:]:
        path = Path(raw)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            outcomes.append(
                {
                    "artifact": path.name,
                    "status": "error",
                    "reason": "ARTIFACT_UNREADABLE_OR_INVALID_JSON",
                }
            )
            continue
        valid = (
            isinstance(data, dict)
            and data.get("schema") == 1
            and isinstance(data.get("ok"), int)
            and data["ok"] in (0, 1)
        )
        if not valid:
            outcomes.append(
                {"artifact": path.name, "status": "error", "reason": "CONTRACT_INVALID"}
            )
        else:
            outcomes.append(
                {
                    "artifact": path.name,
                    "status": "pass" if data["ok"] == 1 else "fail",
                    "check": data.get("check", "unknown"),
                }
            )
    code = (
        2
        if any(x["status"] == "error" for x in outcomes)
        else 1
        if any(x["status"] == "fail" for x in outcomes)
        else 0
    )
    print(
        json.dumps(
            {
                "schema": 1,
                "check": "validate-checks",
                "status": {0: "pass", 1: "fail", 2: "error"}[code],
                "ok": int(code == 0),
                "metrics": {
                    "artifacts": len(outcomes),
                    "passed": sum(x["status"] == "pass" for x in outcomes),
                    "failed": sum(x["status"] == "fail" for x in outcomes),
                    "errors": sum(x["status"] == "error" for x in outcomes),
                },
                "artifacts": outcomes,
            },
            separators=(",", ":"),
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
