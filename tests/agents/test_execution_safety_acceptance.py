import subprocess
from pathlib import Path

import pytest
from agent_runtime.implementer import apply_scoped_patch, normalize_single_file_patch
from agent_runtime.integration import integrate_branches
from agent_runtime.quality_runner import run_gates
from agent_runtime.sandbox import SandboxProfile, run_sandboxed
from agent_runtime.worktrees import create_run_worktree, remove_run_worktree


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=path, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _repository(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    _git(path, "config", "user.name", "Acceptance")
    _git(path, "config", "user.email", "acceptance@example.invalid")
    (path / "src").mkdir()
    (path / "src/app.py").write_text("value = 1\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "base")
    return _git(path, "rev-parse", "HEAD")


def test_run_worktrees_are_unique_and_patches_are_sha_and_path_scoped(tmp_path) -> None:
    repository = tmp_path / "repo"
    base = _repository(repository)
    run_root = tmp_path / "worktrees"
    first = create_run_worktree(repository, run_root, run_id="run-1", base_sha=base)
    second = create_run_worktree(repository, run_root, run_id="run-2", base_sha=base)
    assert first.path != second.path and first.branch != second.branch
    patch = "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n"
    changed = apply_scoped_patch(
        first.path, patch, base_sha=base, allowed_paths=("src/*.py",)
    )
    assert changed == ("src/app.py",)
    assert (first.path / "src/app.py").read_text() == "value = 2\n"
    with pytest.raises(PermissionError, match="PATCH_OUTSIDE_ALLOWED_PATHS"):
        apply_scoped_patch(second.path, patch, base_sha=base, allowed_paths=("README.md",))
    with pytest.raises(ValueError, match="PATCH_BASE_SHA_MISMATCH"):
        apply_scoped_patch(first.path, patch, base_sha="0" * 40, allowed_paths=("src/*.py",))
    remove_run_worktree(repository, first)
    remove_run_worktree(repository, second)


def test_hunk_only_model_patch_is_bound_to_one_allowed_path(tmp_path) -> None:
    repository = tmp_path / "repo"
    base = _repository(repository)
    run = create_run_worktree(repository, tmp_path / "worktrees", run_id="hunk-run", base_sha=base)
    hunk = "@@ -1 +1 @@\n-value = 1\n+value = 2\n"

    normalized = normalize_single_file_patch(hunk, allowed_paths=("src/app.py",))
    changed = apply_scoped_patch(
        run.path, normalized, base_sha=base, allowed_paths=("src/app.py",)
    )

    assert changed == ("src/app.py",)
    assert (run.path / "src/app.py").read_text(encoding="utf-8") == "value = 2\n"
    remove_run_worktree(repository, run)


def test_hunk_only_patch_requires_one_literal_path_and_no_preamble() -> None:
    hunk = "@@ -1 +1 @@\n-value = 1\n+value = 2\n"
    with pytest.raises(ValueError, match="PATCH_PATH_HEADER_REQUIRED"):
        normalize_single_file_patch(hunk, allowed_paths=("src/*.py", "tests/*.py"))
    with pytest.raises(ValueError, match="PATCH_FORMAT_INVALID"):
        normalize_single_file_patch("Here is the patch:\n" + hunk, allowed_paths=("src/app.py",))


def test_sandbox_command_is_networkless_and_mounts_only_run_worktree(tmp_path, monkeypatch) -> None:
    worktree = tmp_path / "run"
    worktree.mkdir()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr("agent_runtime.sandbox.subprocess.run", fake_run)
    profile = SandboxProfile("local/runner@sha256:" + "a" * 64)
    run_sandboxed(worktree, ["pytest", "-q"], profile=profile)
    command = captured["command"]
    assert "--network=none" in command and "--cap-drop=ALL" in command
    assert "--read-only" in command and any(str(worktree.resolve()) in item for item in command)
    assert ".env" not in " ".join(command)


def test_sandbox_rejects_local_secret_files_and_external_symlinks(tmp_path, monkeypatch):
    worktree = tmp_path / "run-with-env"
    worktree.mkdir()
    (worktree / ".env").write_text("LOCAL_SECRET=value", encoding="utf-8")
    monkeypatch.setattr(
        "agent_runtime.sandbox.subprocess.run",
        lambda *_args, **_kwargs: pytest.fail("docker must not start for unsafe worktrees"),
    )
    profile = SandboxProfile("local/runner@sha256:" + "a" * 64)
    with pytest.raises(PermissionError, match="SANDBOX_WORKTREE_CONTAINS_PROTECTED_FILES"):
        run_sandboxed(worktree, ["true"], profile=profile)

    (worktree / ".env").unlink()
    outside = tmp_path / "outside.txt"
    outside.write_text("synthetic", encoding="utf-8")
    (worktree / "escape.txt").symlink_to(outside)
    with pytest.raises(PermissionError, match="SANDBOX_WORKTREE_SYMLINK_ESCAPE"):
        run_sandboxed(worktree, ["true"], profile=profile)


@pytest.mark.parametrize("relative", ["config/.env", "nested/.env.local", "a/b/credentials.json"])
def test_sandbox_rejects_nested_secret_files_before_launch(tmp_path, monkeypatch, relative):
    worktree = tmp_path / "nested-secrets"
    target = worktree / relative
    target.parent.mkdir(parents=True)
    target.write_text("synthetic-secret", encoding="utf-8")
    monkeypatch.setattr(
        "agent_runtime.sandbox.subprocess.run",
        lambda *_args, **_kwargs: pytest.fail("docker must not start for unsafe worktrees"),
    )
    profile = SandboxProfile("local/runner@sha256:" + "b" * 64)
    with pytest.raises(PermissionError, match="SANDBOX_WORKTREE_CONTAINS_PROTECTED_FILES"):
        run_sandboxed(worktree, ["true"], profile=profile)


def test_real_docker_sandbox_cannot_read_unmounted_host_path(tmp_path):
    worktree = tmp_path / "clean-run"
    worktree.mkdir()
    (tmp_path / "host-secret").write_text("host-only-canary", encoding="utf-8")
    profile = SandboxProfile(
        "postgres@sha256:f4610795587492cd4fb887c2dc3de301b813278bb6f616992061141b5f15ac36",
        timeout_seconds=30,
    )
    result = run_sandboxed(
        worktree,
        ["sh", "-c", "test ! -e /host-secret && echo isolated"],
        profile=profile,
    )
    assert result.returncode == 0
    assert result.stdout.decode().strip() == "isolated"


def test_quality_exit_two_is_infrastructure_error_and_blocks_later_gates() -> None:
    called = []
    result = run_gates(
        [("unit", ["pytest"]), ("build", ["pnpm", "build"])],
        execute=lambda argv: called.append(argv) or 2,
    )
    assert result["ok"] == 0
    assert result["gates"][0]["status"] == "error"
    assert result["gates"][1]["status"] == "skipped"
    assert called == [["pytest"]]


def test_integration_requires_clean_isolated_tree_and_green_regression(tmp_path) -> None:
    repository = tmp_path / "repo"
    base = _repository(repository)
    _git(repository, "switch", "-c", "agent/task-1")
    (repository / "src/app.py").write_text("value = 2\n", encoding="utf-8")
    _git(repository, "add", "src/app.py")
    _git(repository, "commit", "-m", "task change")
    integration = create_run_worktree(
        repository, tmp_path / "trees", run_id="integrate", base_sha=base
    )
    result = integrate_branches(
        repository, integration.path, base_sha=base, branches=("agent/task-1",),
        run_regression=lambda _path: {"status": "fail", "ok": 0},
    )
    assert result["status"] == "rejected"
    assert _git(integration.path, "rev-parse", "HEAD") == base
    passed = integrate_branches(
        repository, integration.path, base_sha=base, branches=("agent/task-1",),
        run_regression=lambda _path: {"status": "pass", "ok": 1},
    )
    assert passed["status"] == "ready_for_human_review"
    remove_run_worktree(repository, integration)


def test_integration_aborts_conflicting_branch_and_restores_base(tmp_path) -> None:
    repository = tmp_path / "repo-conflict"
    base = _repository(repository)
    _git(repository, "switch", "-c", "agent/task-conflict")
    (repository / "src/app.py").write_text("value = 2\n", encoding="utf-8")
    _git(repository, "add", "src/app.py")
    _git(repository, "commit", "-m", "agent change")
    first_branch = _git(repository, "rev-parse", "HEAD")
    _git(repository, "switch", "main")
    _git(repository, "switch", "-c", "agent/task-conflict-2")
    (repository / "src/app.py").write_text("value = 3\n", encoding="utf-8")
    _git(repository, "add", "src/app.py")
    _git(repository, "commit", "-m", "conflicting agent change")
    second_branch = _git(repository, "rev-parse", "HEAD")
    integration = create_run_worktree(
        repository, tmp_path / "conflict-trees", run_id="conflict", base_sha=base
    )

    result = integrate_branches(
        repository,
        integration.path,
        base_sha=base,
        branches=("agent/task-conflict", "agent/task-conflict-2"),
        run_regression=lambda _path: pytest.fail("conflicted merge must not run gates"),
    )
    assert result["status"] == "conflict"
    assert _git(integration.path, "rev-parse", "HEAD") == base
    assert _git(repository, "rev-parse", "refs/heads/agent/task-conflict") == first_branch
    assert _git(repository, "rev-parse", "refs/heads/agent/task-conflict-2") == second_branch
    remove_run_worktree(repository, integration)
