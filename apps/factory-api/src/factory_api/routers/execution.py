"""Authenticated requests for grounded discovery and a proposed execution DAG."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from task_engine.models import Demand, RequirementRevision, Task
from task_engine.outbox import enqueue_event

from factory_api.database import get_db
from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/demands", tags=["execution"], dependencies=[Depends(require_operator)]
)


class PlanningRequest(BaseModel):
    base_git_sha: str = Field(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
    context_paths: list[str] = Field(min_length=1, max_length=16)
    idempotency_key: str = Field(min_length=1, max_length=100)
    profile: str = Field(
        default="registry-fullstack",
        pattern=("^(python-fixture|registry-backend|registry-frontend|registry-fullstack)$"),
    )
    fixture_path: str | None = None
    max_output_tokens: int = Field(default=4096, ge=256, le=8192)
    max_attempts: int = Field(default=2, ge=1, le=3)


def request_work(demand_id: str, payload: PlanningRequest, session: Session, stage: str) -> dict:
    from task_engine.execution import validate_execution_spec

    demand = session.get(Demand, demand_id)
    if demand is None:
        raise HTTPException(404, detail={"code": "DEMAND_NOT_FOUND"})
    if stage == "plan":
        revision = session.scalar(
            select(RequirementRevision)
            .where(RequirementRevision.demand_id == demand_id)
            .order_by(RequirementRevision.version.desc())
            .limit(1)
        )
        if revision is None or revision.decision != "approved":
            raise HTTPException(409, detail={"code": "REQUIREMENT_APPROVAL_REQUIRED"})
        if session.scalar(select(Task.id).where(Task.demand_id == demand_id).limit(1)):
            raise HTTPException(409, detail={"code": "PLAN_ALREADY_EXISTS_REVIEW_REQUIRED"})
    spec: dict = {
        "base_git_sha": payload.base_git_sha,
        "context_paths": payload.context_paths,
        "profile": payload.profile,
        "max_output_tokens": payload.max_output_tokens,
        "max_attempts": payload.max_attempts,
    }
    if payload.fixture_path:
        spec["fixture_path"] = payload.fixture_path
    try:
        validate_execution_spec(spec)
        event = enqueue_event(
            session,
            f"planning:{demand_id}:{stage}:{payload.idempotency_key}",
            f"demand.{stage}.requested",
            {"demand_id": demand_id, "spec": spec, "request_id": payload.idempotency_key},
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(409, detail={"code": str(exc)}) from None
    return {"event_id": event.event_id, "status": "queued", "stage": stage}


@router.post("/{demand_id}/discovery", status_code=202)
def discover(demand_id: str, payload: PlanningRequest, session: Session = Depends(get_db)) -> dict:
    return request_work(demand_id, payload, session, "discovery")


@router.post("/{demand_id}/plan", status_code=202)
def plan(demand_id: str, payload: PlanningRequest, session: Session = Depends(get_db)) -> dict:
    return request_work(demand_id, payload, session, "plan")
