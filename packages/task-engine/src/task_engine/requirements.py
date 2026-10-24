from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.models import Demand, RequirementRevision


class RequirementError(ValueError):
    pass


def create_demand(
    session: Session,
    *,
    source: str,
    external_id: str,
    title: str,
    demand_type: str,
    risk: str = "normal",
    repository_id: str = "self",
) -> Demand:
    existing = session.scalar(
        select(Demand).where(Demand.source == source, Demand.external_id == external_id)
    )
    if existing:
        raise RequirementError("DEMAND_ALREADY_EXISTS")
    demand = Demand(
        source=source,
        external_id=external_id,
        title=title,
        demand_type=demand_type,
        risk=risk,
        repository_id=repository_id,
    )
    session.add(demand)
    session.flush()
    return demand


def add_revision(
    session: Session,
    demand: Demand,
    *,
    content: str,
    acceptance: list[str],
) -> RequirementRevision:
    if not content.strip() or not acceptance or any(not item.strip() for item in acceptance):
        raise RequirementError("REQUIREMENT_CONTENT_AND_ACCEPTANCE_REQUIRED")
    revision = RequirementRevision(
        demand_id=demand.id,
        version=demand.version,
        content=content.strip(),
        acceptance=[item.strip() for item in acceptance],
    )
    demand.version += 1
    session.add(revision)
    session.flush()
    return revision


def decide_revision(
    session: Session, revision: RequirementRevision, decision: str
) -> RequirementRevision:
    if revision.decision == "approved":
        raise RequirementError("APPROVED_REVISION_IMMUTABLE")
    if decision not in {"approved", "rejected", "needs_changes"}:
        raise RequirementError("INVALID_REQUIREMENT_DECISION")
    revision.decision = decision
    session.flush()
    return revision


def edit_revision(
    session: Session,
    revision: RequirementRevision,
    *,
    content: str,
    acceptance: list[str],
) -> RequirementRevision:
    if revision.decision == "approved":
        raise RequirementError("APPROVED_REVISION_IMMUTABLE")
    if not content.strip() or not acceptance:
        raise RequirementError("REQUIREMENT_CONTENT_AND_ACCEPTANCE_REQUIRED")
    revision.content = content.strip()
    revision.acceptance = [item.strip() for item in acceptance]
    session.flush()
    return revision
