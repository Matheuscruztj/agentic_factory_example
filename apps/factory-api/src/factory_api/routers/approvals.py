from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from task_engine.models import ApprovalRequest, Demand, Task

from factory_api.database import get_db
from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/approvals", tags=["approvals"], dependencies=[Depends(require_operator)]
)


class ApprovalCreate(BaseModel):
    entity_type: str = Field(pattern="^(demand|task)$")
    entity_id: str = Field(min_length=1, max_length=36)
    requested_by: str = Field(default="agent", min_length=1, max_length=120)


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|changes_requested)$")
    comment: str = Field(min_length=1, max_length=2000)


def current_entity(session: Session, entity_type: str, entity_id: str):
    entity_class = Demand if entity_type == "demand" else Task
    entity = session.get(entity_class, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail={"code": "APPROVAL_ENTITY_NOT_FOUND"})
    version = entity.version if isinstance(entity, Demand) else entity.state_version
    body = {column.name: getattr(entity, column.name) for column in entity.__table__.columns}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    return entity, version, hashlib.sha256(encoded).hexdigest()


@router.get("")
def list_approvals(
    status: str | None = Query(default="pending"), session: Session = Depends(get_db)
) -> list[dict]:
    query = select(ApprovalRequest)
    if status:
        query = query.where(ApprovalRequest.status == status)
    rows = session.scalars(query.order_by(ApprovalRequest.created_at, ApprovalRequest.id)).all()
    return [
        {
            "id": row.id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "entity_version": row.entity_version,
            "payload_hash": row.payload_hash,
            "status": row.status,
            "requested_by": row.requested_by,
            "decision_by": row.decision_by,
            "comment": row.comment,
        }
        for row in rows
    ]


@router.post("", status_code=201)
def request_approval(payload: ApprovalCreate, session: Session = Depends(get_db)) -> dict:
    _, version, payload_hash = current_entity(session, payload.entity_type, payload.entity_id)
    row = ApprovalRequest(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        entity_version=version,
        payload_hash=payload_hash,
        requested_by=payload.requested_by,
    )
    session.add(row)
    session.commit()
    return {
        "id": row.id,
        "status": row.status,
        "payload_hash": row.payload_hash,
        "entity_version": row.entity_version,
    }


@router.post("/{approval_id}/decision")
def decide_approval(
    approval_id: str, payload: ApprovalDecision, session: Session = Depends(get_db)
) -> dict:
    row = session.get(ApprovalRequest, approval_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "APPROVAL_NOT_FOUND"})
    if row.status != "pending":
        if row.status == payload.decision:
            return {"id": row.id, "status": row.status, "decision_by": row.decision_by}
        raise HTTPException(status_code=409, detail={"code": "APPROVAL_ALREADY_DECIDED"})
    if row.requested_by == "operator":
        raise HTTPException(status_code=403, detail={"code": "REQUESTER_CANNOT_APPROVE"})
    _, version, payload_hash = current_entity(session, row.entity_type, row.entity_id)
    if version != row.entity_version or payload_hash != row.payload_hash:
        raise HTTPException(status_code=409, detail={"code": "APPROVAL_SUBJECT_CHANGED"})
    row.status = payload.decision
    row.comment = payload.comment
    row.decision_by = "operator"
    row.decided_at = datetime.now(UTC)
    session.commit()
    return {"id": row.id, "status": row.status, "decision_by": row.decision_by}
