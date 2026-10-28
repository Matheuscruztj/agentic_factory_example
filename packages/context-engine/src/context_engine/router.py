"""Deterministic selection of at most two curated skills."""

from __future__ import annotations

_PRIVILEGED_TERMS = ("ignore policy", "override policy", "reveal secret", "bypass approval")


def route_skills(
    text: str,
    *,
    demand_type: str = "question",
    role: str = "analyst",
    paths: tuple[str, ...] | list[str] = (),
    registry=(),
) -> tuple[str, ...]:
    lowered = text.lower()
    if any(term in lowered for term in _PRIVILEGED_TERMS):
        raise ValueError("UNTRUSTED_SKILL_ACTIVATION_REJECTED")
    simple_question = demand_type == "question" and not any(
        term in lowered for term in ("implement", "build", "test", "plan", "api", "ui")
    )
    if simple_question:
        return ()

    role_skill = {
        "planner": "workflow-planning",
        "backend": "api-development",
        "frontend": "ui-development",
        "qa": "test-analysis",
    }.get(role.lower())
    normalized_paths = tuple(
        path.lower().replace("\\", "/") for path in paths if isinstance(path, str)
    )
    path_skill = None
    if any(path.endswith((".py", ".sql")) or "/api/" in path for path in normalized_paths):
        path_skill = "api-development"
    elif any(
        path.endswith((".tsx", ".ts", ".css", ".html")) or "/ui/" in path
        for path in normalized_paths
    ):
        path_skill = "ui-development"

    candidates: dict[str, float] = {}
    for skill in registry:
        matches = sum(1 for trigger in skill.triggers if trigger.lower() in lowered)
        if matches:
            candidates[skill.id] = matches / max(skill.weight, 1)
    registered = {skill.id for skill in registry}
    for skill_id, boost in ((role_skill, 1.0), (path_skill, 0.75)):
        if skill_id in registered:
            candidates[skill_id] = max(candidates.get(skill_id, 0.0), boost)
    return tuple(sorted(candidates, key=lambda skill_id: (-candidates[skill_id], skill_id))[:2])
