"""Fail-closed Docker runner profile for untrusted task commands."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_runtime.path_policy import validate_worktree


@dataclass(frozen=True, slots=True)
class SandboxProfile:
    image: str
    memory: str = "2g"
    cpus: str = "2"
    pids_limit: int = 128
    timeout_seconds: int = 900

    def validate(self) -> None:
        if not re.fullmatch(
            r"(?:[A-Za-z0-9][A-Za-z0-9._:/-]*@)?sha256:[0-9a-f]{64}", self.image
        ):
            raise ValueError("SANDBOX_IMAGE_MUST_BE_DIGEST_PINNED")
        if not re.fullmatch(r"[1-9][0-9]*[mMgG]", self.memory):
            raise ValueError("INVALID_SANDBOX_MEMORY")
        if not re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)?", self.cpus):
            raise ValueError("INVALID_SANDBOX_CPU_LIMIT")
        if type(self.pids_limit) is not int or not 1 <= self.pids_limit <= 2048:
            raise ValueError("INVALID_SANDBOX_PID_LIMIT")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 7200:
            raise ValueError("INVALID_SANDBOX_TIMEOUT")


def run_sandboxed(
    worktree: Path, argv: list[str], *, profile: SandboxProfile
) -> subprocess.CompletedProcess:
    profile.validate()
    if not argv or len(argv) > 128 or any(
        not isinstance(arg, str) or "\x00" in arg for arg in argv
    ):
        raise ValueError("INVALID_SANDBOX_COMMAND")
    try:
        root = validate_worktree(worktree)
    except PermissionError as exc:
        reason = str(exc)
        if reason == "WORKTREE_SYMLINK_FORBIDDEN":
            raise PermissionError("SANDBOX_WORKTREE_SYMLINK_ESCAPE") from exc
        raise PermissionError("SANDBOX_WORKTREE_CONTAINS_PROTECTED_FILES") from exc
    if "," in str(root):
        raise ValueError("SANDBOX_PATH_UNSUPPORTED")
    if not root.is_dir() or root == Path(root.anchor):
        raise ValueError("SANDBOX_WORKTREE_INVALID")
    command = [
        "docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--memory", profile.memory,
        "--cpus", profile.cpus,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--pids-limit", str(profile.pids_limit), "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",
        "--mount", f"type=bind,src={root},dst=/workspace",
        "--workdir", "/workspace",
        profile.image, *argv,
    ]
    return subprocess.run(
        command, check=False, capture_output=True,
        timeout=profile.timeout_seconds,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
