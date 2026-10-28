"""Shared quality run identity, sanitized source snapshot, logs and result contracts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
QUALITY = ROOT / ".runtime/quality"
RUN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
SOURCE_DIRS = ("apps", "packages", "workers", "scripts")
EXCLUDED_PARTS = {
    ".git",
    ".runtime",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "test-results",
    "playwright-report",
    ".ssh",
    ".aws",
    "secrets",
}


def safe_source(path: str) -> bool:
    parts = Path(path).parts
    name = Path(path).name
    return not (
        not parts
        or Path(path).is_absolute()
        or ".." in parts
        or any(part in EXCLUDED_PARTS for part in parts)
        or name.startswith(".env")
        and name != ".env.example"
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".tsbuildinfo", ".pyc"))
        or name in {"id_rsa", "id_ed25519", "credentials.json"}
    )


def source_manifest(root: Path = ROOT) -> dict:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
        timeout=30,
    )
    files = {}
    for raw in sorted(set(result.stdout.decode().split("\0"))):
        path = root / raw
        if raw and safe_source(raw) and path.is_file():
            if path.is_symlink():
                raise ValueError("QUALITY_SOURCE_SYMLINK_NOT_SUPPORTED")
            files[raw] = hashlib.sha256(path.read_bytes()).hexdigest()
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    return {
        "git_sha": git_sha,
        "source_sha256": hashlib.sha256(encoded).hexdigest(),
        "files_sha256": files,
    }


class QualityContext:
    def __init__(self, check: str, *, run_id: str | None = None) -> None:
        self.check = check
        self.run_id = (
            run_id
            or os.getenv("FACTORY_QUALITY_RUN_ID")
            or (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
        )
        if not RUN_PATTERN.fullmatch(self.run_id):
            raise ValueError("INVALID_QUALITY_RUN_ID")
        self.run_dir = QUALITY / "runs" / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.run_dir / check.removeprefix("quality-")
        self.artifacts.mkdir(parents=True, exist_ok=True)
        manifest_path = self.run_dir / "source-manifest.json"
        if manifest_path.exists():
            self.manifest = json.loads(manifest_path.read_text())
        else:
            self.manifest = source_manifest()
            manifest_path.write_text(json.dumps(self.manifest, indent=2) + "\n")

    def environment(self) -> dict[str, str]:
        return {
            **os.environ,
            "FACTORY_QUALITY_RUN_ID": self.run_id,
            "PYTHONDONTWRITEBYTECODE": "1",
            "CI": "1",
        }

    def snapshot(self) -> Path:
        source = self.run_dir / "source"
        if not source.exists():
            source.mkdir()
            for raw, digest in self.manifest["files_sha256"].items():
                path = ROOT / raw
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or (hashlib.sha256(path.read_bytes()).hexdigest() != digest)
                ):
                    raise ValueError("SOURCE_CHANGED_DURING_QUALITY_RUN")
                target = source / raw
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        reports = {
            self.run_dir / "python/coverage.xml": source / "sonar-reports/python-coverage.xml",
            self.run_dir / "frontend/factory-coverage/lcov.info": source
            / "sonar-reports/factory-web-coverage.lcov",
            self.run_dir / "frontend/registry-coverage/lcov.info": source
            / "sonar-reports/registry-web-coverage.lcov",
        }
        for report, target in reports.items():
            if report.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                if report.name == "coverage.xml":
                    # Sonar runs in a container under /usr/src. Coverage.py records the
                    # host checkout as its XML source path, which Sonar cannot resolve.
                    coverage_xml = report.read_text(encoding="utf-8").replace(
                        str(ROOT), "/usr/src"
                    )
                    target.write_text(coverage_xml, encoding="utf-8")
                else:
                    shutil.copyfile(report, target)
        return source

    def execute(
        self,
        name: str,
        command: list[str],
        *,
        cwd: Path = ROOT,
        timeout: int = 900,
        env: dict | None = None,
        json_output: bool = False,
    ) -> tuple[dict, str]:
        started = monotonic()
        log = self.artifacts / f"{name}.log"
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env or self.environment(),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            output = result.stdout + result.stderr
            machine_output = result.stdout
            raw_code = result.returncode
            code = raw_code if raw_code in (0, 1) else 2
            reason = None
        except FileNotFoundError:
            output, raw_code, code, reason = "Command not found", None, 2, "COMMAND_NOT_FOUND"
            machine_output = output
        except subprocess.TimeoutExpired:
            output, raw_code, code, reason = "Command timed out", None, 2, "TIMEOUT"
            machine_output = output
        log.write_text(output, encoding="utf-8", errors="replace")
        if json_output:
            (self.artifacts / f"{name}.json").write_text(machine_output, encoding="utf-8")
        step = {
            "name": name,
            "status": {0: "pass", 1: "fail", 2: "error"}[code],
            "exit_code": code,
            "tool_exit_code": raw_code,
            "duration_seconds": round(monotonic() - started, 3),
            "artifact": str(log.relative_to(ROOT)),
        }
        if reason:
            step["error"] = reason
        return step, machine_output if json_output else output

    def finish(self, steps: list[dict], *, metrics: dict | None = None, **extra) -> dict:
        code = (
            2
            if any(s["status"] == "error" for s in steps)
            else (1 if any(s["status"] == "fail" for s in steps) else 0)
        )
        if not steps or any(s["status"] not in {"pass", "fail", "error"} for s in steps):
            code = 2
        artifacts = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.artifacts.rglob("*"))
            if p.is_file() and not p.is_symlink()
        }
        result = {
            "schema": 1,
            "check": self.check,
            "status": {0: "pass", 1: "fail", 2: "error"}[code],
            "ok": int(code == 0),
            "exit_code": code,
            "run_id": self.run_id,
            "git_sha": self.manifest["git_sha"],
            "source_sha256": self.manifest["source_sha256"],
            "created_at": datetime.now(UTC).isoformat(),
            "steps": steps,
            "metrics": metrics
            or {
                "steps": len(steps),
                "passed": sum(s["status"] == "pass" for s in steps),
                "failed": sum(s["status"] == "fail" for s in steps),
                "errors": sum(s["status"] == "error" for s in steps),
            },
            "artifact": str(self.artifacts.relative_to(ROOT)),
            "artifacts_sha256": artifacts,
            "errors": [s.get("error", s["name"]) for s in steps if s["status"] != "pass"],
            **extra,
        }
        encoded = json.dumps(result, separators=(",", ":")) + "\n"
        name = self.check.removeprefix("quality-") + ".json"
        (self.run_dir / name).write_text(encoded)
        (QUALITY / name).write_text(encoded)
        return result


def print_result(result: dict) -> int:
    print(json.dumps(result, separators=(",", ":")))
    return int(result["exit_code"])


def python_command(*args: str) -> list[str]:
    return [sys.executable, *args]
