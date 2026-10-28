#!/usr/bin/env python3
"""Best-effort local hardware telemetry probe; missing tools never fail workflows."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/observability/src"))
from observability.gpu import probe


def main() -> int:
    result = {"schema": 1, "check": "hardware-probe", "captured_at": time.time(), **probe()}
    artifact = Path(".runtime/quality/hardware.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
