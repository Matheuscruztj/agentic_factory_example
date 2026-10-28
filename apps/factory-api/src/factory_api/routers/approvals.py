from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from task_engine.execution import ExecutionError, execution_plan
from task_engine.models import (
    ApprovalRequest,
    AuditRecord,
    Demand,
    RequirementRevision,
    Task,
    TaskDependency,
)
from task_engine.outbox import enqueue_event

from factory_api.database import get_db
from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/approvals", tags=["approvals"], dependencies=[Depends(require_operator)]
)


def _canonical_json_value(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


class ApprovalCreate(BaseModel):
    entity_type: str = Field(pattern="^(demand|task)$")
    entity_id: str = Field(min_length=1, max_length=36)
    requested_by: str = Field(default="agent", min_length=1, max_length=120)


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected|changes_requested)$")
    comment: str = Field(min_length=1, max_length=2000)


def current_entity(session: Session, entity_type: str, entity_id: str):
    entity: Demand | Task
    if entity_type == "demand":
        demand = session.get(Demand, entity_id)
        if demand is None:
            raise HTTPException(status_code=404, detail={"code": "APPROVAL_ENTITY_NOT_FOUND"})
        entity = demand
        version = demand.version
    else:
        task = session.get(Task, entity_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"code": "APPROVAL_ENTITY_NOT_FOUND"})
        entity = task
        version = task.state_version
    body = {
        column.name: _canonical_json_value(getattr(entity, column.name))
        for column in entity.__table__.columns
    }
    if entity_type == "demand":
        revisions = session.scalars(
            select(RequirementRevision)
            .where(RequirementRevision.demand_id == entity_id)
            .order_by(RequirementRevision.version)
        ).all()
        tasks = session.scalars(
            select(Task).where(Task.demand_id == entity_id).order_by(Task.id)
        ).all()
        task_ids = [task.id for task in tasks]
        dependencies = (
            session.scalars(
                select(TaskDependency)
                .where(TaskDependency.task_id.in_(task_ids))
                .order_by(TaskDependency.task_id, TaskDependency.depends_on_id)
            ).all()
            if task_ids
            else []
        )
        revision_payloads = [
            {
                "id": revision.id,
                "version": revision.version,
                "content": revision.content,
                "acceptance": revision.acceptance,
                "ears_clauses": revision.ears_clauses,
                "scenarios": revision.scenarios,
                "clarifications": revision.clarifications,
                "decision": revision.decision,
            }
            for revision in revisions
        ]
        plan = {
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "owner_role": task.owner_role,
                    "path_scopes": task.path_scopes,
                    "acceptance": task.acceptance,
                    "risk": task.risk,
                    "execution_spec": task.execution_spec,
                }
                for task in tasks
            ],
            "dependencies": [
                [dependency.task_id, dependency.depends_on_id] for dependency in dependencies
            ],
        }
        body["requirement_revisions"] = revision_payloads
        body["requirement_revision_hashes"] = [
            {
                "id": revision["id"],
                "version": revision["version"],
                "sha256": hashlib.sha256(
                    json.dumps(
                        revision, sort_keys=True, separators=(",", ":"), default=str
                    ).encode()
                ).hexdigest(),
            }
            for revision in revision_payloads
        ]
        body["plan"] = plan
        body["plan_hash"] = hashlib.sha256(
            json.dumps(plan, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
    else:
        task = session.get(Task, entity_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"code": "APPROVAL_ENTITY_NOT_FOUND"})
        demand = session.get(Demand, task.demand_id)
        latest_revision = session.scalar(
            select(RequirementRevision)
            .where(RequirementRevision.demand_id == task.demand_id)
            .order_by(RequirementRevision.version.desc())
            .limit(1)
        )
        dependency_ids = session.scalars(
            select(TaskDependency.depends_on_id)
            .where(TaskDependency.task_id == task.id)
            .order_by(TaskDependency.depends_on_id)
        ).all()
        body["authorization_context"] = {
            "demand_id": task.demand_id,
            "demand_repository_id": demand.repository_id if demand else None,
            "requirement_revision": (
                {
                    "id": latest_revision.id,
                    "version": latest_revision.version,
                    "content": latest_revision.content,
                    "acceptance": latest_revision.acceptance,
                    "ears_clauses": latest_revision.ears_clauses,
                    "scenarios": latest_revision.scenarios,
                    "clarifications": latest_revision.clarifications,
                    "decision": latest_revision.decision,
                }
                if latest_revision
                else None
            ),
            "dependencies": dependency_ids,
            "plan_hash": hashlib.sha256(
                json.dumps(
                    {
                        "task": {
                            "id": task.id,
                            "title": task.title,
                            "owner_role": task.owner_role,
                            "path_scopes": task.path_scopes,
                            "acceptance": task.acceptance,
                            "risk": task.risk,
                            "execution_spec": task.execution_spec,
                        },
                        "dependencies": dependency_ids,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode()
            ).hexdigest(),
        }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()
    return entity, version, hashlib.sha256(encoded).hexdigest(), body


@router.get("")
def list_approvals(
    status: str | None = Query(default="pending"), session: Session = Depends(get_db)
) -> list[dict]:
    query = select(ApprovalRequest)
    if status:
        query = query.where(ApprovalRequest.status == status)
    rows = session.scalars(query.order_by(ApprovalRequest.created_at, ApprovalRequest.id)).all()
    result = []
    for row in rows:
        try:
            _, current_version, current_hash, subject = current_entity(
                session, row.entity_type, row.entity_id
            )
            is_current = current_version == row.entity_version and current_hash == row.payload_hash
        except HTTPException:
            subject, is_current = {}, False
        result.append(
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
                "subject": subject,
                "subject_current": is_current,
            }
        )
    return result


@router.post("", status_code=201)
def request_approval(
    payload: ApprovalCreate,
    session: Session = Depends(get_db),
    actor: dict = Depends(require_operator),
) -> dict:
    _, version, payload_hash, _ = current_entity(session, payload.entity_type, payload.entity_id)
    row = ApprovalRequest(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        entity_version=version,
        payload_hash=payload_hash,
        requested_by=payload.requested_by,
    )
    session.add(row)
    session.flush()
    session.add(
        AuditRecord(
            subject_type="approval",
            subject_id=row.id,
            action="approval.requested",
            actor=actor.get("sub", "operator"),
            details={"entity_type": row.entity_type, "entity_id": row.entity_id},
        )
    )
    session.commit()
    return {
        "id": row.id,
        "status": row.status,
        "payload_hash": row.payload_hash,
        "entity_version": row.entity_version,
    }


@router.post("/{approval_id}/decision")
def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    session: Session = Depends(get_db),
    actor: dict = Depends(require_operator),
) -> dict:
    row = session.get(ApprovalRequest, approval_id)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "APPROVAL_NOT_FOUND"})
    if row.status != "pending":
        if row.status == payload.decision:
            return {"id": row.id, "status": row.status, "decision_by": row.decision_by}
        raise HTTPException(status_code=409, detail={"code": "APPROVAL_ALREADY_DECIDED"})
    decision_actor = actor.get("sub", "operator")
    if row.requested_by == decision_actor:
        raise HTTPException(status_code=403, detail={"code": "REQUESTER_CANNOT_APPROVE"})
    _, version, payload_hash, _ = current_entity(session, row.entity_type, row.entity_id)
    if version != row.entity_version or payload_hash != row.payload_hash:
        raise HTTPException(status_code=409, detail={"code": "APPROVAL_SUBJECT_CHANGED"})
    changed = session.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.status == "pending",
            ApprovalRequest.entity_version == version,
            ApprovalRequest.payload_hash == payload_hash,
        )
        .values(
            status=payload.decision,
            comment=payload.comment,
            decision_by=decision_actor,
            decided_at=datetime.now(UTC),
        )
    )
    if getattr(changed, "rowcount", None) != 1:
        session.rollback()
        raise HTTPException(status_code=409, detail={"code": "APPROVAL_ALREADY_DECIDED"})
    session.add(
        AuditRecord(
            subject_type="approval",
            subject_id=row.id,
            action="approval.decided",
            actor=decision_actor,
            details={"decision": payload.decision},
        )
    )
    _, _, _, approval_subject = current_entity(session, row.entity_type, row.entity_id)
    execution_snapshot = None
    if payload.decision == "approved":
        demand_id = row.entity_id
        if row.entity_type == "task":
            subject_task = session.get(Task, row.entity_id)
            assert subject_task is not None
            demand_id = subject_task.demand_id
        try:
            execution_snapshot = execution_plan(session, demand_id)
        except ExecutionError:
            # A generic review decision remains useful, but grants no execution.
            execution_snapshot = None
    enqueue_event(
        session,
        event_id=f"approval-decided:{row.id}",
        event_type="human.approval.decided",
        payload={
            "approval_id": row.id,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "entity_version": row.entity_version,
            "payload_hash": row.payload_hash,
            "authorization_context": approval_subject.get("authorization_context"),
            "plan_hash": approval_subject.get("plan_hash"),
            "requirement_revision_hashes": approval_subject.get(
                "requirement_revision_hashes"
            ),
            "decision": payload.decision,
            "execution_plan": execution_snapshot,
            "actor": decision_actor,
        },
    )
    session.commit()
    return {"id": row.id, "status": payload.decision, "decision_by": decision_actor}
