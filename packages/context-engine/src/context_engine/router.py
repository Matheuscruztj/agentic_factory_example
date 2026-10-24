"""Deterministic selection of at most two curated skills."""

from __future__ import annotations

_PRIVILEGED_TERMS = ("ignore policy", "override policy", "reveal secret", "bypass approval")


def route_skills(
    text: str, *, demand_type: str = "question", role: str = "analyst", registry=()
) -> tuple[str, ...]:
    lowered = text.lower()
    if any(term in lowered for term in _PRIVILEGED_TERMS):
        raise ValueError("UNTRUSTED_SKILL_ACTIVATION_REJECTED")
    candidates = []
    for skill in registry:
        matches = sum(1 for trigger in skill.triggers if trigger.lower() in lowered)
        if matches:
            candidates.append((matches / max(skill.weight, 1), skill.id))
    if demand_type == "question" and not any(
        term in lowered for term in ("implement", "build", "test", "plan", "api", "ui")
    ):
        return ()
    candidates.sort(key=lambda row: (-row[0], row[1]))
    return tuple(skill_id for _, skill_id in candidates[:2])
