from agent_runtime.workflows.proposal_graph import follow_up


def test_completed_demand_qa_followup_reuses_prior_snapshot_and_skips_discovery():
    calls = []
    proposal = {
        "id": "qa-follow-up-demo",
        "payload_hash": "f" * 64,
        "snapshot_sha": "a" * 40,
        "original_demand_id": "demand-1",
    }
    approval = {
        "status": "approved",
        "proposal_id": proposal["id"],
        "payload_hash": proposal["payload_hash"],
    }

    def run_followup(task_id, context):
        calls.append((task_id, context))
        return "follow-up-run-1"

    result = follow_up(
        proposal,
        approval=approval,
        create_task=lambda _proposal: "task-follow-up-1",
        invoke_subworkflow=run_followup,
    )
    assert result == "follow-up-run-1"
    assert calls == [
        ("task-follow-up-1", {"snapshot_sha": "a" * 40, "discovery": "reuse"})
    ]
    assert proposal["original_demand_id"] == "demand-1"
