from __future__ import annotations

import pytest
from task_engine.requirement_draft import draft_requirement


def test_requirement_draft_keeps_missing_conditions_explicit_and_unapproved() -> None:
    draft = draft_requirement(
        "Add a filtered customer export",
        ["the operator can export the filtered results as CSV"],
    )

    assert draft.approved is False
    assert draft.clauses[0].requires_clarification is True
    assert "[condition to clarify]" in draft.clauses[0].ears_candidate
    assert [scenario.polarity for scenario in draft.scenarios] == ["positive", "negative"]
    assert all(scenario.requires_clarification for scenario in draft.scenarios)


def test_requirement_draft_preserves_explicit_ears_condition() -> None:
    draft = draft_requirement(
        "Protect secret values",
        ["When a secret is logged, the system shall redact its value"],
    )

    clause = draft.clauses[0]
    assert clause.condition == "a secret is logged"
    assert clause.response == "redact its value"
    assert clause.requires_clarification is False
    assert draft.scenarios[0].requires_clarification is False


def test_requirement_draft_rejects_empty_or_malformed_acceptance() -> None:
    with pytest.raises(ValueError, match="REQUIREMENT_DRAFT_INPUT_REQUIRED"):
        draft_requirement("Requirement", [])
    with pytest.raises(ValueError, match="REQUIREMENT_ACCEPTANCE_INVALID"):
        draft_requirement("Requirement", [""])
