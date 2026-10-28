"""Shared fail-closed path policy for worktrees and generated patches."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path, PurePosixPath


def validate_relative_path(value: str) -> str:
    if not value or "\x00" in value or "\\" in value:
        raise PermissionError("PATH_INVALID")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise PermissionError("PATH_INVALID")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PermissionError("PATH_INVALID")
    if any(_sensitive_part(part) for part in path.parts):
        raise PermissionError("PATH_PROTECTED")
    return path.as_posix()


def validate_worktree(root: Path) -> Path:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir() or resolved == Path(resolved.anchor):
        raise PermissionError("WORKTREE_INVALID")
    for current, directories, files in os.walk(resolved, followlinks=False):
        parent = Path(current)
        for name in [*directories, *files]:
            candidate = parent / name
            relative = candidate.relative_to(resolved).as_posix()
            validate_relative_path(relative)
            metadata = candidate.lstat()
            if candidate.is_symlink():
                raise PermissionError("WORKTREE_SYMLINK_FORBIDDEN")
            if candidate.is_file() and metadata.st_nlink > 1:
                raise PermissionError("WORKTREE_HARDLINK_FORBIDDEN")
    return resolved


def validate_patch_paths(root: Path, patch: str, allowed_paths: tuple[str, ...]) -> set[str]:
    rename_headers = ("rename from ", "rename to ", "copy from ", "copy to ")
    if any(line.startswith(rename_headers) for line in patch.splitlines()):
        raise PermissionError("PATCH_RENAME_FORBIDDEN")
    paths: set[str] = set()
    for line in patch.splitlines():
        if line.startswith(("GIT binary patch", "Binary files ")):
            raise PermissionError("PATCH_BINARY_FORBIDDEN")
        if line.startswith(("+++ ", "--- ")):
            raw = line[4:].split("\t", 1)[0]
            if raw == "/dev/null":
                continue
            if not raw.startswith(("a/", "b/")):
                raise PermissionError("PATCH_PATH_INVALID")
            relative = validate_relative_path(raw[2:])
            if ".git" in PurePosixPath(relative).parts:
                raise PermissionError("PATCH_PATH_PROTECTED")
            target = root / relative
            for parent in [target, *target.parents]:
                if parent == root.parent:
                    break
                if parent.exists() and parent.is_symlink():
                    raise PermissionError("PATCH_SYMLINK_FORBIDDEN")
            if target.exists() and target.is_file() and target.stat().st_nlink > 1:
                raise PermissionError("PATCH_HARDLINK_FORBIDDEN")
            if not any(fnmatch.fnmatchcase(relative, pattern) for pattern in allowed_paths):
                raise PermissionError("PATCH_OUTSIDE_ALLOWED_PATHS")
            paths.add(relative)
    if not paths:
        raise PermissionError("PATCH_PATHS_REQUIRED")
    return paths


def _sensitive_part(part: str) -> bool:
    name = part.casefold()
    return (
        name in {".ssh", ".aws", ".gnupg", "secrets", "credentials"}
        or (name.startswith(".env") and name != ".env.example")
        or name in {"id_rsa", "id_ed25519", "credentials.json", "known_hosts"}
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".keystore"))
    )
