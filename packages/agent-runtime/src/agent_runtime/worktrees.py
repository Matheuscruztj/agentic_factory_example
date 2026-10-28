"""Per-run isolated Git worktree lifecycle with immutable base references."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RunWorktree:
    run_id: str
    path: Path
    branch: str
    base_sha: str


def create_run_worktree(repository: Path, root: Path, *, run_id: str, base_sha: str) -> RunWorktree:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise ValueError("INVALID_RUN_ID")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", base_sha):
        raise ValueError("INVALID_BASE_SHA")
    repo = repository.resolve(strict=True)
    root.mkdir(parents=True, exist_ok=True)
    worktree_root = root.resolve(strict=True)
    if worktree_root == repo or repo in worktree_root.parents or worktree_root in repo.parents:
        raise ValueError("WORKTREE_ROOT_MUST_BE_OUTSIDE_REPOSITORY")
    destination = worktree_root / run_id
    if destination.exists():
        raise FileExistsError("RUN_WORKTREE_ALREADY_EXISTS")
    _git(repo, "cat-file", "-e", f"{base_sha}^{{commit}}")
    branch = f"agent/run-{run_id}"
    _git(repo, "worktree", "add", "--detach", str(destination), base_sha)
    try:
        _git(destination, "switch", "-c", branch)
        actual = _git(destination, "rev-parse", "HEAD").strip()
        if actual != base_sha:
            raise RuntimeError("WORKTREE_BASE_SHA_MISMATCH")
    except BaseException:
        _git(repo, "worktree", "remove", "--force", str(destination), check=False)
        raise
    return RunWorktree(run_id, destination, branch, base_sha)


def remove_run_worktree(repository: Path, worktree: RunWorktree) -> None:
    _git(repository.resolve(strict=True), "worktree", "remove", "--force", str(worktree.path))


def _git(cwd: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=False, capture_output=True, text=True, timeout=30
    )
    if check and result.returncode:
        raise RuntimeError(f"GIT_OPERATION_FAILED:{args[0]}")
    return result.stdout
