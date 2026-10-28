"""Operator-only, immutable feedback for completed agent runs."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from task_engine.models import AgentRun, AuditRecord, Demand, RunFeedback, Task

from factory_api.config import Settings
from factory_api.database import get_db
from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/evals", tags=["eval-feedback"], dependencies=[Depends(require_operator)]
)
_HASH = re.compile(r"^[a-f0-9]{64}$")
_CATEGORIES = {"requirements", "implementation", "tests", "policy", "reliability", "other"}


class FeedbackCreate(BaseModel):
    run_id: str
    task_id: str
    demand_id: str | None = None
    decision: str
    error_category: str | None = None
    comment: str = Field(default="", max_length=2000)
    prompt_hash: str
    model_id: str = Field(min_length=1, max_length=120)
    requirement_version: int = Field(ge=1)
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)


@router.post("/feedback", status_code=201)
def create_feedback(
    payload: FeedbackCreate,
    operator: dict = Depends(require_operator),
    db: Session = Depends(get_db),
) -> dict:
    if not Settings.from_env().auth_enabled:
        raise HTTPException(status_code=403, detail={"code": "AUTH_REQUIRED_FOR_FEEDBACK"})
    try:
        run_id = str(UUID(payload.run_id))
        task_id = str(UUID(payload.task_id))
        demand_id = str(UUID(payload.demand_id)) if payload.demand_id else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "IDENTIFIER_INVALID"}) from exc
    if payload.decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail={"code": "DECISION_INVALID"})
    if payload.error_category is not None and payload.error_category not in _CATEGORIES:
        raise HTTPException(status_code=422, detail={"code": "ERROR_CATEGORY_INVALID"})
    if not _HASH.fullmatch(payload.prompt_hash):
        raise HTTPException(status_code=422, detail={"code": "PROMPT_HASH_INVALID"})
    if payload.decision == "reject" and payload.error_category is None:
        raise HTTPException(status_code=422, detail={"code": "REJECTION_CATEGORY_REQUIRED"})
    if payload.decision == "approve" and payload.error_category is not None:
        raise HTTPException(status_code=422, detail={"code": "APPROVAL_HAS_ERROR_CATEGORY"})
    for reference in payload.evidence_refs:
        if not reference or len(reference) > 500 or reference.startswith(("/", "../")):
            raise HTTPException(status_code=422, detail={"code": "EVIDENCE_REFERENCE_INVALID"})
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND"})
    run = db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"})
    if run.task_id != task_id:
        raise HTTPException(status_code=422, detail={"code": "RUN_TASK_MISMATCH"})
    if run.status not in {"review", "completed", "failed"}:
        raise HTTPException(status_code=409, detail={"code": "RUN_NOT_REVIEWABLE"})
    if payload.requirement_version != task.expected_demand_version:
        raise HTTPException(status_code=409, detail={"code": "REQUIREMENT_VERSION_MISMATCH"})
    if demand_id and demand_id != task.demand_id:
        raise HTTPException(status_code=422, detail={"code": "TASK_DEMAND_MISMATCH"})
    demand_id = demand_id or task.demand_id
    if db.get(Demand, demand_id) is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    row = RunFeedback(
        run_id=run_id,
        task_id=task_id,
        demand_id=demand_id,
        reviewer_sub=operator.get("sub", "operator"),
        decision=payload.decision,
        error_category=payload.error_category,
        comment=payload.comment.strip(),
        prompt_hash=payload.prompt_hash,
        model_id=payload.model_id,
        requirement_version=payload.requirement_version,
        evidence_refs=payload.evidence_refs,
    )
    db.add(row)
    db.add(
        AuditRecord(
            subject_type="run",
            subject_id=run_id,
            action="eval.feedback.recorded",
            actor=operator.get("sub", "operator"),
            details={
                "decision": payload.decision,
                "feedback_id": row.id,
                "task_id": task_id,
                "model_id": payload.model_id,
                "requirement_version": payload.requirement_version,
            },
            evidence_hashes=[payload.prompt_hash],
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "FEEDBACK_ALREADY_RECORDED"}) from exc
    except Exception:
        db.rollback()
        raise
    db.refresh(row)
    return {
        "id": row.id,
        "run_id": row.run_id,
        "decision": row.decision,
        "reviewer_sub": row.reviewer_sub,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/feedback/summary")
def feedback_summary(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(RunFeedback.decision, RunFeedback.error_category, func.count()).group_by(
            RunFeedback.decision, RunFeedback.error_category
        )
    ).all()
    approved = sum(count for decision, _, count in rows if decision == "approve")
    rejected = sum(count for decision, _, count in rows if decision == "reject")
    categories = {
        category: count
        for decision, category, count in rows
        if decision == "reject" and category is not None
    }
    total = approved + rejected
    return {
        "feedback_count": total,
        "first_pass_rate": approved / total if total else None,
        "rework_count": rejected,
        "error_categories": categories,
    }
