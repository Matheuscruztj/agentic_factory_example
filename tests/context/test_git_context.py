import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from context_engine.git_context import (
    GitContextError,
    load_curated_skills,
    open_snapshot,
    read_authorized_file,
    retrieve_context,
)


def _repository(root: Path) -> str:
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True
    )
    (root / "README.md").write_text("searchable text\ncontact test@example.com\n", encoding="utf-8")
    (root / ".env").write_text("TOKEN=do-not-read\n", encoding="utf-8")
    (root / ".env.example").write_text("TOKEN=placeholder\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests/fixture.txt").write_text("searchable text\n", encoding="utf-8")
    (root / "link.txt").symlink_to("README.md")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "--quiet", "-m", "fixture"], check=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def test_snapshot_is_commit_pinned_and_excludes_secrets_tests_and_links(tmp_path):
    repository = tmp_path / "repo"
    commit = _repository(repository)
    snapshot = open_snapshot(repository, commit, authorize_commit=lambda value: value == commit)

    assert snapshot.commit == commit
    assert "README.md" in snapshot.files
    assert ".env.example" in snapshot.files
    assert ".env" not in snapshot.files
    assert "tests/fixture.txt" not in snapshot.files
    assert "link.txt" not in snapshot.files
    with pytest.raises(GitContextError, match="GIT_COMMIT_SHA_INVALID"):
        open_snapshot(repository, "bad", authorize_commit=lambda _: True)
    with pytest.raises(GitContextError, match="GIT_COMMIT_NOT_AUTHORIZED"):
        open_snapshot(repository, commit, authorize_commit=lambda _: False)


def test_authorized_file_reads_only_snapshot_blob_with_limits(tmp_path):
    repository = tmp_path / "repo"
    commit = _repository(repository)
    snapshot = open_snapshot(repository, commit, authorize_commit=lambda _: True)

    content = read_authorized_file(
        snapshot, "README.md", allowed_paths={"README.md"}, max_bytes=100
    )
    assert content["commit"] == commit
    assert content["blob_sha"] == snapshot.blobs["README.md"]
    assert "searchable text" in content["text"]
    with pytest.raises(GitContextError, match="REPOSITORY_PATH_NOT_AUTHORIZED"):
        read_authorized_file(snapshot, ".env.example", allowed_paths={"README.md"})
    with pytest.raises(GitContextError, match="REPOSITORY_CONTEXT_LIMIT_INVALID"):
        read_authorized_file(snapshot, "README.md", allowed_paths={"README.md"}, max_bytes=0)
    with pytest.raises(GitContextError, match="REPOSITORY_FILE_TOO_LARGE"):
        read_authorized_file(snapshot, "README.md", allowed_paths={"README.md"}, max_bytes=1)


def test_context_search_is_scoped_redacted_and_skill_files_are_hash_pinned(tmp_path):
    repository = tmp_path / "repo"
    commit = _repository(repository)
    snapshot = open_snapshot(repository, commit, authorize_commit=lambda _: True)
    pack = retrieve_context(
        snapshot,
        "searchable text",
        allowed_paths={"README.md", "tests/fixture.txt", ".env"},
        max_snippets=2,
    )
    assert pack.content["sources"] == ["README.md"]
    assert "test@example.com" not in json.dumps(pack.content)
    with pytest.raises(GitContextError, match="GIT_CONTEXT_QUERY_INVALID"):
        retrieve_context(snapshot, " ", allowed_paths={"README.md"})
    with pytest.raises(GitContextError, match="GIT_CONTEXT_SNIPPET_LIMIT_INVALID"):
        retrieve_context(snapshot, "text", allowed_paths={"README.md"}, max_snippets=0)

    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    skill = skill_dir / "review.md"
    skill.write_text("Review safely.", encoding="utf-8")
    registry = skill_dir / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "version": 1,
                "skills": [
                    {
                        "id": "review",
                        "version": "1",
                        "triggers": ["review"],
                        "weight": 1,
                        "file": skill.name,
                        "sha256": hashlib.sha256(skill.read_bytes()).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert load_curated_skills(registry, ["review"])[0]["content"] == "Review safely."
    with pytest.raises(GitContextError, match="CURATED_SKILL_NOT_FOUND"):
        load_curated_skills(registry, ["other"])
