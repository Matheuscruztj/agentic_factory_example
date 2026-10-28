"""Structured check runner that preserves fail, error, and skipped distinctions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    status: str
    exit_code: int | None
    duration_ms: int


def run_sandbox_gates(worktree: Path, gates, *, profile):
    """Execute named argv gates in the network-disabled task sandbox."""
    from agent_runtime.sandbox import run_sandboxed

    return run_gates(
        gates,
        execute=lambda argv: run_sandboxed(worktree, list(argv), profile=profile).returncode,
    )


def run_gates(
    gates: Sequence[tuple[str, Sequence[str]]], *,
    execute: Callable[[Sequence[str]], int], clock: Callable[[], float] = monotonic,
) -> dict:
    results = []
    stopped = False
    for name, argv in gates:
        if not name or not argv:
            raise ValueError("INVALID_QUALITY_GATE")
        if stopped:
            results.append(GateResult(name, "skipped", None, 0))
            continue
        started = clock()
        try:
            code = execute(argv)
        except Exception:
            code = None
            status = "error"
        else:
            status = "pass" if code == 0 else "fail" if code == 1 else "error"
        elapsed = max(0, int((clock() - started) * 1000))
        results.append(GateResult(name, status, code, elapsed))
        stopped = status != "pass"
    return {
        "schema": 1,
        "check": "quality-gates",
        "status": "pass" if results and all(row.status == "pass" for row in results) else "fail",
        "ok": int(bool(results) and all(row.status == "pass" for row in results)),
        "gates": [asdict(row) for row in results],
    }
