"""Normalize local coding-quality tool results into stable 0/1/2 outcomes."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool: str
    status: str
    exit_code: int
    duration_ms: int
    artifact: str | None
    artifact_sha256: str | None
    error_class: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _redact(text: str) -> str:
    text = re.sub(r"(?i)(bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(
        r"(?i)(api[_-]?key|token|password|secret)(\s*[:=]\s*)[^\s,;]+", r"\1\2[REDACTED]", text
    )
    return text


def run_quality_tool(
    command: list[str],
    *,
    tool: str,
    artifact_dir: Path,
    timeout_seconds: int = 300,
    optional: bool = False,
) -> ToolResult:
    """Execute one local tool, redact its log and classify quality vs infrastructure."""
    if not command or timeout_seconds < 1 or timeout_seconds > 3600:
        raise ValueError("QUALITY_TOOL_ARGUMENT_INVALID")
    started = monotonic()
    path = artifact_dir / f"{tool}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    executable = shutil.which(command[0])
    error: str | None
    if executable is None:
        if optional:
            return ToolResult(tool, "skipped", 0, round((monotonic() - started) * 1000), None, None)
        output, code, error = "TOOL_NOT_INSTALLED\n", 2, "infrastructure"
    else:
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            output = result.stdout + result.stderr
            code = result.returncode if result.returncode in {0, 1} else 2
            error = None if code == 0 else "code" if code == 1 else "infrastructure"
        except subprocess.TimeoutExpired:
            output, code, error = "TOOL_TIMEOUT\n", 2, "infrastructure"
        except OSError:
            output, code, error = "TOOL_EXECUTION_FAILED\n", 2, "infrastructure"
    safe = _redact(output[:1_000_000])
    path.write_text(safe, encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ToolResult(
        tool,
        {0: "pass", 1: "fail", 2: "error"}[code],
        code,
        round((monotonic() - started) * 1000),
        path.as_posix(),
        digest,
        error,
    )
