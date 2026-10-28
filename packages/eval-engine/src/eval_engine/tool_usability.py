"""Outcome-based tool usability metrics with explicit no-tool controls."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, slots=True)
class ToolTrial:
    case_id: str
    arm: str
    selected_tool: bool
    selection_correct: bool
    arguments_valid: bool
    recovered_after_error: bool
    relevant_evidence_found: bool
    tool_calls: int
    unproductive_calls: int
    tokens: int
    outcome_passed: bool


def report_tool_usability(trials: list[ToolTrial], *, run_id: str) -> dict:
    if not run_id or not trials:
        raise ValueError("TOOL_TRIALS_AND_RUN_REQUIRED")
    if any(
        not row.case_id
        or row.arm not in {"tool", "no_tool"}
        or row.tool_calls < 0
        or row.unproductive_calls < 0
        or row.unproductive_calls > row.tool_calls
        or row.tokens < 0
        or (row.arm == "no_tool" and (row.selected_tool or row.tool_calls != 0))
        for row in trials
    ):
        raise ValueError("TOOL_TRIAL_INVALID")
    result = {}
    for arm in ("tool", "no_tool"):
        rows = [row for row in trials if row.arm == arm]
        if not rows:
            continue
        selected = [row for row in rows if row.selected_tool]
        result[arm] = {
            "cases": len({row.case_id for row in rows}),
            "attempts": len(rows),
            "outcome_pass_rate": mean(row.outcome_passed for row in rows),
            "tool_selection_accuracy": (
                mean(row.selection_correct for row in selected) if selected else None
            ),
            "argument_valid_rate": mean(row.arguments_valid for row in selected)
            if selected
            else None,
            "error_recovery_rate": mean(row.recovered_after_error for row in selected)
            if selected
            else None,
            "relevant_evidence_rate": mean(row.relevant_evidence_found for row in selected)
            if selected
            else None,
            "tool_calls": sum(row.tool_calls for row in rows),
            "unproductive_calls": sum(row.unproductive_calls for row in rows),
            "tokens": sum(row.tokens for row in rows),
        }
    return {
        "schema": 1,
        "run_id": run_id,
        "metrics_by_arm": result,
        "tool_order_required": False,
        "automatic_tool_policy_change": False,
    }
