"""Versioned requirement refinement with approved-revision immutability."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.audit import record_audit
from task_engine.models import Demand, RequirementRevision
from task_engine.requirements import RequirementError, add_revision


def refine_requirement(
    session: Session,
    demand: Demand,
    *,
    content: str,
    acceptance: list[str],
    operator_comment: str,
) -> RequirementRevision:
    if not operator_comment.strip():
        raise RequirementError("OPERATOR_COMMENT_REQUIRED")
    approved = session.scalar(
        select(RequirementRevision).where(
            RequirementRevision.demand_id == demand.id,
            RequirementRevision.decision == "approved",
        )
    )
    revision = add_revision(session, demand, content=content, acceptance=acceptance)
    if approved is not None and revision.version <= approved.version:
        raise RequirementError("REVISION_VERSION_NOT_MONOTONIC")
    record_audit(
        session,
        subject_type="requirement_revision",
        subject_id=revision.id,
        action="requirement_refined",
        actor="operator",
        details={"operator_comment": operator_comment.strip(), "version": revision.version},
    )
    return revision
