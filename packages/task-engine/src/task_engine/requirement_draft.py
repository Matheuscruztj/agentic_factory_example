"""EARS-oriented, non-authoritative drafts for progressive requirement refinement."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class RequirementScenario:
    case_id: str
    polarity: str
    action: str
    expected: str
    requires_clarification: bool


@dataclass(frozen=True, slots=True)
class RequirementClause:
    source_acceptance: str
    ears_candidate: str
    condition: str | None
    response: str
    requires_clarification: bool


@dataclass(frozen=True, slots=True)
class RequirementDraft:
    source_text: str
    clauses: tuple[RequirementClause, ...]
    scenarios: tuple[RequirementScenario, ...]
    approved: bool = False

    def as_dict(self) -> dict:
        return {
            "source_text": self.source_text,
            "clauses": [asdict(item) for item in self.clauses],
            "scenarios": [asdict(item) for item in self.scenarios],
            "approved": self.approved,
        }


_EARS = re.compile(
    r"^(?:when|if|while|where|sempre que|se|enquanto|onde)\s+(.+?),\s*"
    r"(?:the system shall|o sistema deve)\s+(.+)$",
    flags=re.IGNORECASE,
)


def draft_requirement(text: str, acceptance: list[str]) -> RequirementDraft:
    """Turn operator-supplied acceptance into reviewable EARS/scenario drafts.

    The helper never invents a trigger or approves a requirement. Missing EARS
    conditions remain explicit placeholders and require clarification.
    """
    source = text.strip() if isinstance(text, str) else ""
    if not source or not isinstance(acceptance, list) or not acceptance:
        raise ValueError("REQUIREMENT_DRAFT_INPUT_REQUIRED")
    clauses: list[RequirementClause] = []
    scenarios: list[RequirementScenario] = []
    for index, raw in enumerate(acceptance, start=1):
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("REQUIREMENT_ACCEPTANCE_INVALID")
        criterion = raw.strip()
        match = _EARS.fullmatch(criterion)
        if match:
            condition, response = match.groups()
            candidate = criterion
            needs_clarification = False
        else:
            condition = None
            response = criterion
            candidate = f"WHEN [condition to clarify], THE SYSTEM SHALL {criterion}"
            needs_clarification = True
        clauses.append(
            RequirementClause(
                source_acceptance=criterion,
                ears_candidate=candidate,
                condition=condition,
                response=response,
                requires_clarification=needs_clarification,
            )
        )
        scenarios.extend(
            (
                RequirementScenario(
                    case_id=f"acceptance-{index}-positive",
                    polarity="positive",
                    action=(
                        f"Exercise the confirmed condition: {condition}"
                        if condition
                        else "Exercise the condition after it is clarified."
                    ),
                    expected=response,
                    requires_clarification=needs_clarification,
                ),
                RequirementScenario(
                    case_id=f"acceptance-{index}-negative",
                    polarity="negative",
                    action=(
                        f"Violate or omit the confirmed condition: {condition}"
                        if condition
                        else "Exercise a case that does not satisfy the clarified condition."
                    ),
                    expected="This acceptance criterion must not be reported as satisfied.",
                    requires_clarification=needs_clarification,
                ),
            )
        )
    return RequirementDraft(source, tuple(clauses), tuple(scenarios))
