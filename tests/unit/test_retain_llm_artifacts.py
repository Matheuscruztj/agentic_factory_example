import os
from datetime import UTC, datetime, timedelta

from scripts.retain_llm_artifacts import apply_retention, plan_retention


def test_retention_deletes_only_expired_raw_trials_and_keeps_audit(tmp_path):
    trials = tmp_path / "trials"
    trials.mkdir()
    stale = trials / "old-run.jsonl"
    current = trials / "current-run.jsonl"
    stale.write_text('{"raw":true}\n')
    current.write_text('{"raw":false}\n')
    old_time = (datetime.now(UTC) - timedelta(days=50)).timestamp()
    stale.touch()
    os.utime(stale, (old_time, old_time))
    now = datetime.now(UTC)
    plan = plan_retention(trials, max_age_days=30, now=now)
    assert [item["path"] for item in plan["candidates"]] == ["old-run.jsonl"]
    assert apply_retention(plan, trials) == ["old-run.jsonl"]
    assert not stale.exists()
    assert current.exists()


def test_retention_rejects_changed_candidate_after_plan(tmp_path):
    trials = tmp_path / "trials"
    trials.mkdir()
    stale = trials / "old.jsonl"
    stale.write_text("before")
    old_time = (datetime.now(UTC) - timedelta(days=50)).timestamp()
    os.utime(stale, (old_time, old_time))
    plan = plan_retention(trials, max_age_days=30, now=datetime.now(UTC))
    stale.write_text("changed")
    try:
        apply_retention(plan, trials)
    except ValueError as exc:
        assert str(exc) == "TRIAL_CHANGED_AFTER_PLAN"
    else:
        raise AssertionError("changed candidate must not be deleted")
    assert stale.exists()


def test_retention_rejects_refreshed_timestamp_or_path_escape(tmp_path):
    trials = tmp_path / "trials"
    trials.mkdir()
    stale = trials / "old.jsonl"
    stale.write_text("same content")
    old_time = (datetime.now(UTC) - timedelta(days=50)).timestamp()
    os.utime(stale, (old_time, old_time))
    plan = plan_retention(trials, max_age_days=30, now=datetime.now(UTC))
    os.utime(stale, None)
    try:
        apply_retention(plan, trials)
    except ValueError as exc:
        assert str(exc) == "TRIAL_CHANGED_AFTER_PLAN"
    else:
        raise AssertionError("refreshed candidate must not be deleted")
    escaped = {"candidates": [{"path": "../protected.jsonl", "sha256": "0" * 64}]}
    try:
        apply_retention(escaped, trials)
    except ValueError as exc:
        assert str(exc) == "TRIAL_PATH_INVALID"
    else:
        raise AssertionError("path traversal must be rejected")
