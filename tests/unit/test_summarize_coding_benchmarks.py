from __future__ import annotations

import json

from scripts.summarize_coding_benchmarks import summarize


def test_summary_does_not_count_response_only_trials_as_accepted(tmp_path):
    trials = tmp_path / "trials.jsonl"
    trials.write_text(
        "\n".join(
            json.dumps(
                {
                    "route": route,
                    "latency_ms": 1000,
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "task_size": "small",
                }
            )
            for route in ("direct", "proxy")
        )
        + "\n"
    )
    report = summarize([trials])
    assert report["status"] == "inconclusive_no_accepted_patch_trials"
    for route in ("direct", "proxy"):
        metrics = report["routes"][route]
        assert metrics["accepted_tasks"] == 0
        assert metrics["accepted_tasks_per_hour"] == 0
        assert metrics["tokens_per_accepted_task"] is None
        assert metrics["functional_pass_rate"] is None
        assert metrics["task_size_strata"]["small"]["trials"] == 1
        assert metrics["task_size_strata"]["long"]["trials"] == 0
    assert report["winner"] is None
