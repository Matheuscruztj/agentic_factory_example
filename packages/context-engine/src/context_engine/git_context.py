"""Read-only context retrieval pinned to an authorized Git commit."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from context_engine.pack import ContextPack, build_context_pack
from context_engine.skill_registry import load_registry


class GitContextError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    root: Path
    commit: str
    files: frozenset[str]
    blobs: dict[str, str]


def load_curated_skills(registry_path: Path, skill_ids: list[str]) -> list[dict]:
    if len(skill_ids) > 2 or len(set(skill_ids)) != len(skill_ids):
        raise GitContextError("CONTEXT_SKILL_LIMIT_EXCEEDED")
    registry = load_registry(registry_path)
    by_id = {skill.id: skill for skill in registry}
    payload = []
    for skill_id in skill_ids:
        skill = by_id.get(skill_id)
        if skill is None:
            raise GitContextError("CURATED_SKILL_NOT_FOUND")
        raw_path = registry_path.resolve().parent / skill.file
        path = raw_path.resolve(strict=True)
        if raw_path.is_symlink() or path.parent != registry_path.resolve().parent:
            raise GitContextError("CURATED_SKILL_PATH_INVALID")
        payload.append(
            {
                "id": skill.id,
                "version": skill.version,
                "sha256": skill.sha256,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return payload


def read_authorized_file(
    snapshot: RepositorySnapshot,
    path: str,
    *,
    allowed_paths: set[str],
    max_bytes: int = 64_000,
) -> dict:
    if path not in allowed_paths or path not in snapshot.files or _excluded(path):
        raise GitContextError("REPOSITORY_PATH_NOT_AUTHORIZED")
    if type(max_bytes) is not int or not 1 <= max_bytes <= 1_000_000:
        raise GitContextError("REPOSITORY_CONTEXT_LIMIT_INVALID")
    size_text = _git(snapshot.root, "cat-file", "-s", snapshot.blobs[path]).strip()
    if not size_text.isdigit() or int(size_text) > max_bytes:
        raise GitContextError("REPOSITORY_FILE_TOO_LARGE")
    content = _git(snapshot.root, "show", f"{snapshot.commit}:{path}").encode()
    return {
        "path": path,
        "blob_sha": snapshot.blobs[path],
        "commit": snapshot.commit,
        "text": content.decode("utf-8", errors="replace"),
    }


def open_snapshot(
    repository: Path,
    commit: str,
    *,
    authorize_commit,
) -> RepositorySnapshot:
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise GitContextError("GIT_COMMIT_SHA_INVALID")
    root = repository.resolve(strict=True)
    if not root.is_dir() or _git(root, "rev-parse", "--show-toplevel").strip() != str(root):
        raise GitContextError("GIT_REPOSITORY_REQUIRED")
    if not authorize_commit(commit):
        raise GitContextError("GIT_COMMIT_NOT_AUTHORIZED")
    if _git(root, "cat-file", "-t", commit).strip() != "commit":
        raise GitContextError("GIT_COMMIT_NOT_FOUND")
    listing = _git(root, "ls-tree", "-r", "-z", commit)
    files: set[str] = set()
    blobs: dict[str, str] = {}
    for record in listing.split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, object_type, object_id = metadata.split(" ", 2)
        if object_type != "blob" or mode in {"120000", "160000"} or _excluded(path):
            continue
        files.add(path)
        blobs[path] = object_id
    return RepositorySnapshot(root, commit, frozenset(files), blobs)


def retrieve_context(
    snapshot: RepositorySnapshot,
    query: str,
    *,
    allowed_paths: set[str],
    skills: list[dict] | None = None,
    artifact_refs: list[dict] | None = None,
    max_tokens: int = 4000,
    max_snippets: int = 8,
) -> ContextPack:
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise GitContextError("GIT_CONTEXT_QUERY_INVALID")
    if max_snippets < 1 or max_snippets > 32:
        raise GitContextError("GIT_CONTEXT_SNIPPET_LIMIT_INVALID")
    if len(skills or []) > 2:
        raise GitContextError("CONTEXT_SKILL_LIMIT_EXCEEDED")
    scope = {path for path in allowed_paths if path in snapshot.files and not _excluded(path)}
    candidates = sorted(scope)
    selected: list[dict] = []
    for path in candidates:
        output = _git(
            snapshot.root,
            "grep",
            "-n",
            "-I",
            "-F",
            "-e",
            query,
            snapshot.commit,
            "--",
            path,
            allow_failure=True,
        )
        if not output:
            continue
        for line in output.splitlines():
            # git grep emits COMMIT:path:line:text because the treeish is supplied.
            prefix = f"{snapshot.commit}:{path}:"
            if not line.startswith(prefix):
                continue
            number, sep, text = line[len(prefix) :].partition(":")
            if not sep or not number.isdigit():
                continue
            selected.append(
                {
                    "path": path,
                    "blob_sha": snapshot.blobs[path],
                    "line": int(number),
                    "text": text,
                }
            )
            if len(selected) >= max_snippets:
                break
        if len(selected) >= max_snippets:
            break
    task = {"id": "repository-context", "title": query, "git_commit": snapshot.commit}
    return build_context_pack(
        task=task,
        skills=skills or [],
        snippets=selected,
        artifacts=artifact_refs or [],
        allowed_paths=scope,
        max_tokens=max_tokens,
    )


def _excluded(path: str) -> bool:
    parts = Path(path).parts
    lowered = {part.casefold() for part in parts}
    basename = Path(path).name.casefold()
    return (
        bool(lowered & {".git", ".ssh", ".aws", "secrets", "evals", "holdout"})
        or any(part in {"tests", "test", "fixtures"} for part in lowered)
        or (basename.startswith(".env") and basename != ".env.example")
        or basename.endswith((".pem", ".key", ".p12", ".pfx"))
    )


def _git(root: Path, *args: str, allow_failure: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if result.returncode and not allow_failure and result.returncode != 0:
        raise GitContextError("GIT_CONTEXT_COMMAND_FAILED")
    if allow_failure and result.returncode not in {0, 1}:
        raise GitContextError("GIT_CONTEXT_SEARCH_FAILED")
    return result.stdout
