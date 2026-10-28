"""Prepare a private integration worktree and require regression gates before approval."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path


def integrate_branches(
    repository: Path,
    integration_worktree: Path,
    *,
    base_sha: str,
    branches: Sequence[str],
    run_regression: Callable[[Path], dict],
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40,64}", base_sha) or not branches:
        raise ValueError("INVALID_INTEGRATION_REQUEST")
    root = integration_worktree.resolve(strict=True)
    repo = repository.resolve(strict=True)
    if not (root / ".git").is_file():
        raise ValueError("INTEGRATION_WORKTREE_REQUIRED")
    if _git(root, "rev-parse", "HEAD") != base_sha:
        raise ValueError("INTEGRATION_BASE_SHA_MISMATCH")
    if _git(root, "status", "--porcelain"):
        raise ValueError("INTEGRATION_WORKTREE_MUST_BE_CLEAN")
    summaries = []
    for branch in branches:
        if not re.fullmatch(r"[A-Za-z0-9._/-]{1,160}", branch) or branch.startswith("-"):
            raise ValueError("INVALID_BRANCH_REF")
        commit = _git(repo, "rev-parse", "--verify", f"{branch}^{{commit}}")
        merge = subprocess.run(
            ["git", "merge", "--no-ff", "--no-edit", commit],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if merge.returncode:
            _git(root, "merge", "--abort", check=False)
            _git(root, "reset", "--hard", base_sha, check=False)
            return {"status": "conflict", "branch": branch, "merged": summaries}
        summaries.append({"branch": branch, "commit": commit})
    try:
        gates = run_regression(root)
    except Exception:
        _git(root, "reset", "--hard", base_sha, check=False)
        raise
    if gates.get("ok") != 1 or gates.get("status") != "pass":
        _git(root, "reset", "--hard", base_sha)
        return {"status": "rejected", "merged": summaries, "gates": gates}
    return {"status": "ready_for_human_review", "merged": summaries, "gates": gates}


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False, timeout=30
    )
    if check and result.returncode:
        raise RuntimeError("GIT_OPERATION_FAILED")
    return result.stdout.strip()
