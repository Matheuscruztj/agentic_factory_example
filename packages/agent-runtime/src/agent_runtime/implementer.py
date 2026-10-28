"""Scoped, base-pinned patch application inside a per-run worktree."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from agent_runtime.path_policy import validate_patch_paths, validate_relative_path


def normalize_single_file_patch(patch: str, *, allowed_paths: tuple[str, ...]) -> str:
    """Attach the sole authorized path to a model diff that contains only hunks.

    Some local coding models return unified hunks without Git file headers. This
    accepts that narrow form only for one literal allowed path; prose, malformed
    hunks, and multi-file scopes remain rejected. The normal patch validator
    checks the resulting path before application.
    """
    if not isinstance(patch, str) or not patch.strip() or len(patch) > 2_000_000:
        raise ValueError("PATCH_FORMAT_INVALID")
    lines = patch.splitlines()
    if any(
        line.startswith(("diff --git ", "--- ", "+++ ", "GIT binary patch", "Binary files "))
        for line in lines[:3]
    ):
        return patch
    if len(allowed_paths) != 1:
        raise ValueError("PATCH_PATH_HEADER_REQUIRED")
    path = allowed_paths[0]
    if any(character in path for character in "*?["):
        raise ValueError("PATCH_PATH_HEADER_REQUIRED")
    try:
        path = validate_relative_path(path)
    except PermissionError as exc:
        raise ValueError("PATCH_PATH_INVALID") from exc
    if not lines or not re.fullmatch(
        r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", lines[0]
    ):
        raise ValueError("PATCH_FORMAT_INVALID")
    normalized_hunks: list[str] = []
    index = 0
    while index < len(lines):
        match = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", lines[index])
        if match is None:
            raise ValueError("PATCH_FORMAT_INVALID")
        index += 1
        body: list[str] = []
        old_count = 0
        new_count = 0
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if not line:
                raise ValueError("PATCH_FORMAT_INVALID")
            if line[0] == " ":
                old_count += 1
                new_count += 1
            elif line[0] == "-":
                old_count += 1
            elif line[0] == "+":
                new_count += 1
            elif not line.startswith("\\"):
                raise ValueError("PATCH_FORMAT_INVALID")
            body.append(line)
            index += 1
        old_start, _, new_start, _, suffix = match.groups()
        normalized_hunks.append(
            f"@@ -{old_start},{old_count} +{new_start},{new_count} @@{suffix}"
        )
        normalized_hunks.extend(body)
    hunk_text = "\n".join(normalized_hunks)
    return f"--- a/{path}\n+++ b/{path}\n{hunk_text}\n"


def apply_scoped_patch(
    worktree: Path, patch: str, *, base_sha: str, allowed_paths: tuple[str, ...]
) -> tuple[str, ...]:
    if (
        not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", base_sha)
        or not patch
        or len(patch) > 2_000_000
    ):
        raise ValueError("INVALID_PATCH_REQUEST")
    root = worktree.resolve(strict=True)
    head = _git(root, "rev-parse", "HEAD")
    if head != base_sha:
        raise ValueError("PATCH_BASE_SHA_MISMATCH")
    paths = validate_patch_paths(root, patch, allowed_paths)
    diff = subprocess.run(
        ["git", "apply", "--check", "--whitespace=error"], cwd=root, input=patch,
        text=True, capture_output=True, check=False, timeout=30,
    )
    if diff.returncode:
        raise ValueError("PATCH_VALIDATION_FAILED")
    applied = subprocess.run(
        ["git", "apply", "--whitespace=error"], cwd=root, input=patch,
        text=True, capture_output=True, check=False, timeout=30,
    )
    if applied.returncode:
        raise RuntimeError("PATCH_APPLY_FAILED")
    return tuple(sorted(paths))


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False, timeout=30
    )
    if result.returncode:
        raise RuntimeError("GIT_OPERATION_FAILED")
    return result.stdout.strip()
