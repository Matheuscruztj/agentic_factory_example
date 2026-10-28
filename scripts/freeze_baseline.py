#!/usr/bin/env python3
"""Write a reproducibility manifest only for a clean, committed repository snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False, timeout=20
    )
    if result.returncode:
        raise ValueError("GIT_SNAPSHOT_UNAVAILABLE")
    return result.stdout.strip()


def _hash_paths(root: Path, paths: list[Path]) -> dict[str, str]:
    if not paths:
        raise ValueError("BASELINE_INPUTS_REQUIRED")
    files = {}
    for relative in sorted(paths):
        candidate = root / relative
        try:
            path = candidate.resolve(strict=True)
        except OSError:
            raise ValueError("BASELINE_INPUT_PATH_INVALID") from None
        path_parts = [candidate, *candidate.parents]
        if (
            root not in path.parents
            or not path.is_file()
            or any(part.is_symlink() for part in path_parts if part != root.parent)
        ):
            raise ValueError("BASELINE_INPUT_PATH_INVALID")
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def freeze(
    root: Path,
    commit: str,
    fixtures: list[Path],
    expected_results: list[Path],
    external_tests: list[Path],
) -> dict:
    if git(root, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("WORKTREE_NOT_CLEAN")
    head = git(root, "rev-parse", "HEAD")
    requested = git(root, "rev-parse", f"{commit}^{{commit}}")
    if requested != head:
        raise ValueError("BASELINE_MUST_MATCH_REVIEWED_HEAD")
    file_hashes = {
        "fixtures": _hash_paths(root, fixtures),
        "expected_results": _hash_paths(root, expected_results),
        "external_tests": _hash_paths(root, external_tests),
    }
    tree = git(root, "rev-parse", f"{head}^{{tree}}")
    return {
        "schema": 1,
        "git_commit": head,
        "git_tree": tree,
        "inputs_sha256": file_hashes,
        "manifest_sha256": hashlib.sha256(
            json.dumps(
                {"git_commit": head, "git_tree": tree, "inputs_sha256": file_hashes},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--fixture", action="append", default=[], type=Path)
    parser.add_argument("--expected-result", action="append", default=[], type=Path)
    parser.add_argument("--external-test", action="append", default=[], type=Path)
    parser.add_argument("--output", type=Path, default=Path(".runtime/baseline/manifest.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        manifest = freeze(
            root, args.commit, args.fixture, args.expected_result, args.external_test
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"check": "freeze-baseline", "status": "error", "reason": str(exc)}))
        return 2
    destination = root / args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"check": "freeze-baseline", "status": "pass", "commit": manifest["git_commit"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
