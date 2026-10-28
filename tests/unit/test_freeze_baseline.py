import subprocess
from pathlib import Path

import pytest

from scripts.freeze_baseline import freeze


def _repo(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"],
        check=True,
    )
    (root / "fixture.json").write_text('{"case":"synthetic"}\n', encoding="utf-8")
    (root / "expected.json").write_text('{"status":"pass"}\n', encoding="utf-8")
    (root / "test_contract.py").write_text("def test_contract(): pass\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture baseline"], check=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_freeze_records_commit_tree_and_all_independent_inputs(tmp_path):
    commit = _repo(tmp_path)

    result = freeze(
        tmp_path,
        commit,
        [Path("fixture.json")],
        [Path("expected.json")],
        [Path("test_contract.py")],
    )

    assert result["git_commit"] == commit
    assert len(result["git_tree"]) == 40
    assert set(result["inputs_sha256"]) == {"fixtures", "expected_results", "external_tests"}
    assert len(result["manifest_sha256"]) == 64


@pytest.mark.parametrize("change", ["tracked", "untracked"])
def test_freeze_rejects_dirty_worktree_without_creating_a_commit(tmp_path, change):
    commit = _repo(tmp_path)
    if change == "tracked":
        (tmp_path / "fixture.json").write_text("changed\n", encoding="utf-8")
    else:
        (tmp_path / "untracked.txt").write_text("not committed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="WORKTREE_NOT_CLEAN"):
        freeze(
            tmp_path,
            commit,
            [Path("fixture.json")],
            [Path("expected.json")],
            [Path("test_contract.py")],
        )
    head = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == commit


def test_freeze_rejects_different_commit_and_missing_external_test(tmp_path):
    commit = _repo(tmp_path)
    (tmp_path / "later.txt").write_text("later\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "later.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "later change"], check=True)
    with pytest.raises(ValueError, match="BASELINE_MUST_MATCH_REVIEWED_HEAD"):
        freeze(
            tmp_path,
            commit,
            [Path("fixture.json")],
            [Path("expected.json")],
            [Path("test_contract.py")],
        )
    current = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    with pytest.raises(ValueError, match="BASELINE_INPUT_PATH_INVALID"):
        freeze(
            tmp_path,
            current,
            [Path("fixture.json")],
            [Path("expected.json")],
            [Path("missing_test.py")],
        )
