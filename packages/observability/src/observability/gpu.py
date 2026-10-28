"""Best-effort NVIDIA telemetry; missing tools never fail workflows."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def probe() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return {"status": "unavailable", "source": "nvidia-smi", "reason": "NOT_INSTALLED"}
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,memory.used,utilization.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "source": "nvidia-smi", "reason": type(exc).__name__}
    if result.returncode != 0:
        return {"status": "unavailable", "source": "nvidia-smi", "reason": "PROBE_FAILED"}
    devices = []
    for line in result.stdout.splitlines():
        values = [item.strip() for item in line.split(",")]
        if len(values) == 5:
            devices.append(
                {
                    "name": values[0],
                    "memory_total_mib": _number(values[1]),
                    "memory_used_mib": _number(values[2]),
                    "utilization_percent": _number(values[3]),
                    "power_watts": _number(values[4]),
                }
            )
    return {
        "status": "available" if devices else "unavailable",
        "source": "nvidia-smi",
        "devices": devices,
    }


def _number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None
