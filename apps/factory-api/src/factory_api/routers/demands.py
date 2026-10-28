from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.responses import Response
from task_engine.dependencies import add_dependencies
from task_engine.models import (
    AgentRun,
    Artifact,
    AuditRecord,
    Demand,
    GateEvidence,
    RequirementRevision,
    Task,
    TaskDependency,
    TransitionEvent,
)
from task_engine.requirements import (
    RequirementError,
    add_revision,
    create_demand,
    decide_revision,
)
from task_engine.scheduler import run_fake_demand
from task_engine.transitions import TransitionError, apply_transition

from factory_api.database import get_db
from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/demands", tags=["demands"], dependencies=[Depends(require_operator)]
)
tasks_router = APIRouter(
    prefix="/api/v1/tasks", tags=["tasks"], dependencies=[Depends(require_operator)]
)


class DemandCreate(BaseModel):
    source: str = Field(min_length=1, max_length=32)
    external_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    demand_type: str = Field(min_length=1, max_length=32)
    risk: str = Field(default="normal", max_length=16)
    repository_id: str = Field(default="self", max_length=80)
    requirement: str = Field(min_length=1)
    acceptance: list[str] = Field(default_factory=list)


class RequirementRevisionCreate(BaseModel):
    expected_demand_version: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=20_000)
    acceptance: list[str] = Field(min_length=1, max_length=20)


class RequirementRevisionDecision(BaseModel):
    expected_demand_version: int = Field(ge=1)
    revision_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    decision: str = Field(pattern="^(approved|rejected|needs_changes)$")
    comment: str = Field(min_length=1, max_length=2_000)


class DemandView(BaseModel):
    id: str
    source: str
    external_id: str
    title: str
    demand_type: str
    status: str
    version: int
    state_version: int
    risk: str
    repository_id: str

    @classmethod
    def from_model(cls, row: Demand) -> DemandView:
        return cls.model_validate({name: getattr(row, name) for name in cls.model_fields})


class TaskView(BaseModel):
    id: str
    demand_id: str
    title: str
    owner_role: str
    status: str
    priority: int
    path_scopes: list[str]
    acceptance: list[str]
    risk: str
    state_version: int
    dependencies: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    runs: list[dict] = Field(default_factory=list)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    owner_role: str = Field(min_length=1, max_length=64)
    priority: int = Field(default=50, ge=0, le=100)
    path_scopes: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    risk: str = Field(default="normal", max_length=16)
    dependencies: list[str] = Field(default_factory=list)
    execution_spec: dict = Field(default_factory=dict)


class TaskTransition(BaseModel):
    new_state: str = Field(min_length=1, max_length=24)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=160)


class TaskPlanUpdate(TaskCreate):
    expected_version: int = Field(ge=1)


@router.post("/{demand_id}/transition")
def transition_demand(
    demand_id: str,
    payload: TaskTransition,
    session: Session = Depends(get_db),
    actor: dict = Depends(require_operator),
) -> dict:
    demand = session.get(Demand, demand_id)
    if demand is None:
        raise HTTPException(404, detail={"code": "DEMAND_NOT_FOUND"})
    try:
        event = apply_transition(
            session,
            demand,
            entity_type="demand",
            new_state=payload.new_state,
            expected_version=payload.expected_version,
            actor=actor.get("sub", "operator"),
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )
        session.commit()
    except TransitionError as exc:
        session.rollback()
        raise HTTPException(409, detail={"code": str(exc)}) from None
    return {
        "id": demand.id,
        "status": demand.status,
        "state_version": demand.state_version,
        "transition_id": event.id,
    }


@tasks_router.put("/{task_id}/plan")
def update_proposed_task_plan(
    task_id: str,
    payload: TaskPlanUpdate,
    session: Session = Depends(get_db),
    actor: dict = Depends(require_operator),
) -> dict:
    """Revise an unexecuted plan without duplicating tasks or retaining stale grants."""
    from sqlalchemy import delete
    from task_engine.execution import validate_execution_spec

    task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
    if task is None:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND"})
    if task.status not in {"proposed", "blocked"} or task.state_version != payload.expected_version:
        raise HTTPException(409, detail={"code": "TASK_PLAN_NOT_EDITABLE"})
    if session.scalar(
        select(AgentRun.id)
        .where(AgentRun.task_id == task.id, AgentRun.status == "running")
        .limit(1)
    ):
        raise HTTPException(409, detail={"code": "TASK_RUN_STILL_ACTIVE"})
    try:
        validate_execution_spec(payload.execution_spec)
        known = session.scalars(select(Task.id).where(Task.demand_id == task.demand_id)).all()
        if not set(payload.dependencies).issubset(known):
            raise ValueError("TASK_DEPENDENCY_OUTSIDE_DEMAND")
        session.execute(delete(TaskDependency).where(TaskDependency.task_id == task.id))
        add_dependencies(session, known, [(task.id, dep) for dep in payload.dependencies])
        for key in (
            "title",
            "owner_role",
            "priority",
            "path_scopes",
            "acceptance",
            "risk",
            "execution_spec",
        ):
            setattr(task, key, getattr(payload, key))
        task.state_version += 1
        session.add(
            AuditRecord(
                subject_type="task",
                subject_id=task.id,
                action="task.plan_revised",
                actor=actor.get("sub", "operator"),
                details={
                    "previous_version": payload.expected_version,
                    "authorization": "new_plan_approval_required",
                },
            )
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, detail={"code": str(exc)}) from None
    return {"id": task.id, "state_version": task.state_version, "status": task.status}


def _requirement_revision_sha256(revision: RequirementRevision) -> str:
    payload = {
        "demand_id": revision.demand_id,
        "version": revision.version,
        "content": revision.content,
        "acceptance": revision.acceptance,
        "ears_clauses": revision.ears_clauses,
        "scenarios": revision.scenarios,
        "clarifications": revision.clarifications,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _find_idempotent_replay(session: Session, payload: DemandCreate) -> tuple[Demand | None, bool]:
    existing = session.scalar(
        select(Demand).where(
            Demand.source == payload.source,
            Demand.external_id == payload.external_id,
        )
    )
    if existing is None:
        return None, False
    latest_revision = session.scalar(
        select(RequirementRevision)
        .where(RequirementRevision.demand_id == existing.id)
        .order_by(RequirementRevision.version.desc())
    )
    same_request = (
        existing.title == payload.title
        and existing.demand_type == payload.demand_type
        and existing.risk == payload.risk
        and existing.repository_id == payload.repository_id
        and latest_revision is not None
        and latest_revision.content == payload.requirement.strip()
        and latest_revision.acceptance == [item.strip() for item in payload.acceptance]
    )
    return existing, same_request


@router.post("", response_model=DemandView, status_code=201)
def create_demand_endpoint(payload: DemandCreate, session: Session = Depends(get_db)) -> DemandView:
    try:
        existing, same_request = _find_idempotent_replay(session, payload)
        if existing is not None:
            if same_request:
                return DemandView.from_model(existing)
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"},
            )
        row = create_demand(
            session,
            source=payload.source,
            external_id=payload.external_id,
            title=payload.title,
            demand_type=payload.demand_type,
            risk=payload.risk,
            repository_id=payload.repository_id,
        )
        add_revision(session, row, content=payload.requirement, acceptance=payload.acceptance)
        session.add(
            AuditRecord(
                subject_type="demand",
                subject_id=row.id,
                action="demand.created",
                actor="operator",
                details={"source": row.source, "demand_type": row.demand_type},
            )
        )
        session.commit()
        return DemandView.from_model(row)
    except RequirementError as exc:
        session.rollback()
        code = str(exc)
        raise HTTPException(
            status_code=409 if "EXISTS" in code else 422, detail={"code": code}
        ) from None
    except IntegrityError:
        session.rollback()
        existing, same_request = _find_idempotent_replay(session, payload)
        if existing is not None and same_request:
            return DemandView.from_model(existing)
        code = (
            "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"
            if existing is not None
            else "DEMAND_ALREADY_EXISTS"
        )
        raise HTTPException(status_code=409, detail={"code": code}) from None


@router.post("/{demand_id}/revisions", status_code=201)
def create_requirement_revision(
    demand_id: str,
    payload: RequirementRevisionCreate,
    session: Session = Depends(get_db),
    actor: dict = Depends(require_operator),
) -> dict:
    demand = session.scalar(select(Demand).where(Demand.id == demand_id).with_for_update())
    if demand is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    if demand.version != payload.expected_demand_version:
        raise HTTPException(status_code=409, detail={"code": "DEMAND_VERSION_STALE"})
    try:
        revision = add_revision(
            session,
            demand,
            content=payload.content,
            acceptance=payload.acceptance,
        )
        digest = _requirement_revision_sha256(revision)
        session.add(
            AuditRecord(
                subject_type="requirement_revision",
                subject_id=revision.id,
                action="requirement_revision.created",
                actor=actor.get("sub", "operator"),
                details={
                    "demand_id": demand.id,
                    "version": revision.version,
                    "revision_sha256": digest,
                },
            )
        )
        session.commit()
    except RequirementError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from None
    return {
        "id": revision.id,
        "demand_id": demand.id,
        "version": revision.version,
        "decision": revision.decision,
        "revision_sha256": digest,
        "ears_clauses": revision.ears_clauses,
        "scenarios": revision.scenarios,
        "clarifications": revision.clarifications,
    }


@router.post("/{demand_id}/revisions/{revision_version}/decision")
def decide_requirement_revision_endpoint(
    demand_id: str,
    revision_version: int,
    payload: RequirementRevisionDecision,
    session: Session = Depends(get_db),
    actor: dict = Depends(require_operator),
) -> dict:
    demand = session.scalar(select(Demand).where(Demand.id == demand_id).with_for_update())
    if demand is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    if demand.version != payload.expected_demand_version:
        raise HTTPException(status_code=409, detail={"code": "DEMAND_VERSION_STALE"})
    revision = session.scalar(
        select(RequirementRevision)
        .where(
            RequirementRevision.demand_id == demand_id,
            RequirementRevision.version == revision_version,
        )
        .with_for_update()
    )
    if revision is None:
        raise HTTPException(status_code=404, detail={"code": "REQUIREMENT_REVISION_NOT_FOUND"})
    digest = _requirement_revision_sha256(revision)
    if digest != payload.revision_sha256:
        raise HTTPException(status_code=409, detail={"code": "REQUIREMENT_REVISION_HASH_STALE"})
    if revision.decision == payload.decision:
        return {
            "demand_id": demand.id,
            "revision_id": revision.id,
            "version": revision.version,
            "decision": revision.decision,
            "revision_sha256": digest,
            "decision_by": actor.get("sub", "operator"),
            "replayed": True,
        }
    if revision.decision != "proposed":
        raise HTTPException(status_code=409, detail={"code": "REQUIREMENT_REVISION_DECIDED"})
    try:
        decide_revision(session, revision, payload.decision)
    except RequirementError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail={"code": str(exc)}) from None
    actor_id = actor.get("sub", "operator")
    session.add(
        AuditRecord(
            subject_type="requirement_revision",
            subject_id=revision.id,
            action=f"requirement_revision.{payload.decision}",
            actor=actor_id,
            details={
                "demand_id": demand.id,
                "version": revision.version,
                "revision_sha256": digest,
                "comment": payload.comment.strip(),
            },
        )
    )
    from task_engine.outbox import enqueue_event

    enqueue_event(
        session,
        event_id=f"requirement-revision-decision:{revision.id}",
        event_type="requirement.revision.decided",
        payload={
            "demand_id": demand.id,
            "revision_id": revision.id,
            "revision_version": revision.version,
            "revision_sha256": digest,
            "decision": payload.decision,
            "actor": actor_id,
        },
    )
    session.commit()
    return {
        "demand_id": demand.id,
        "revision_id": revision.id,
        "version": revision.version,
        "decision": revision.decision,
        "revision_sha256": digest,
        "decision_by": actor_id,
        "replayed": False,
    }


@router.get("", response_model=list[DemandView])
def list_demands(
    status: str | None = Query(
        default=None,
        pattern=r"^(new|triage|discovery|clarification_pending|refined|approved|planned|executing|verifying|human_review|blocked|failed|follow_up_required|completed|cancelled)$",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db),
) -> list[DemandView]:
    query = select(Demand)
    if status:
        query = query.where(Demand.status == status)
    return [
        DemandView.from_model(row)
        for row in session.scalars(query.order_by(Demand.updated_at.desc(), Demand.id).limit(limit))
    ]


@router.get("/{demand_id}")
def get_demand(demand_id: str, session: Session = Depends(get_db)) -> dict:
    demand = session.get(Demand, demand_id)
    if demand is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    tasks = session.scalars(
        select(Task).where(Task.demand_id == demand_id).order_by(Task.created_at, Task.id)
    ).all()
    revisions = session.scalars(
        select(RequirementRevision)
        .where(RequirementRevision.demand_id == demand_id)
        .order_by(RequirementRevision.version)
    ).all()
    deps = (
        session.scalars(
            select(TaskDependency).where(TaskDependency.task_id.in_([t.id for t in tasks]))
        ).all()
        if tasks
        else []
    )
    by_task: dict[str, list[str]] = {}
    for dep in deps:
        by_task.setdefault(dep.task_id, []).append(dep.depends_on_id)
    task_ids = [task.id for task in tasks]
    run_rows = (
        session.scalars(
            select(AgentRun)
            .where(AgentRun.task_id.in_(task_ids))
            .order_by(AgentRun.task_id, AgentRun.attempt)
        ).all()
        if task_ids
        else []
    )
    run_ids = [run.id for run in run_rows]
    gate_rows = (
        session.scalars(
            select(GateEvidence)
            .where(GateEvidence.run_id.in_(run_ids))
            .order_by(GateEvidence.run_id, GateEvidence.check_name)
        ).all()
        if run_ids
        else []
    )
    artifacts = (
        session.scalars(
            select(Artifact).where(Artifact.subject_type == "run", Artifact.subject_id.in_(run_ids))
        ).all()
        if run_ids
        else []
    )
    transitions = (
        session.scalars(
            select(TransitionEvent)
            .where(
                TransitionEvent.entity_type == "task",
                TransitionEvent.entity_id.in_(task_ids),
            )
            .order_by(TransitionEvent.created_at.desc())
        ).all()
        if task_ids
        else []
    )
    gates_by_run: dict[str, list[dict]] = {}
    for gate in gate_rows:
        gates_by_run.setdefault(gate.run_id, []).append(
            {
                "check_name": gate.check_name,
                "status": gate.status,
                "git_sha": gate.git_sha,
                "artifact_sha256": gate.artifact_sha256,
            }
        )
    artifacts_by_run: dict[str, list[dict]] = {}
    for artifact in artifacts:
        artifacts_by_run.setdefault(artifact.subject_id, []).append(
            {
                "id": artifact.id,
                "path": artifact.relative_path,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
                "media_type": artifact.media_type,
            }
        )
    runs_by_task: dict[str, list[dict]] = {}
    for run in run_rows:
        runs_by_task.setdefault(run.task_id, []).append(
            {
                "id": run.id,
                "attempt": run.attempt,
                "status": run.status,
                "executor_kind": run.executor_kind,
                "base_git_sha": run.base_git_sha,
                "result_git_sha": run.result_git_sha,
                "tree_hash": run.tree_hash,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "gates": gates_by_run.get(run.id, []),
                "artifacts": artifacts_by_run.get(run.id, []),
            }
        )
    blocked_reason_by_task: dict[str, str] = {}
    for event in transitions:
        if event.entity_id not in blocked_reason_by_task and event.to_state == "blocked":
            blocked_reason_by_task[event.entity_id] = event.reason
    return {
        "demand": DemandView.from_model(demand),
        "revisions": [
            {
                "id": r.id,
                "version": r.version,
                "content": r.content,
                "acceptance": r.acceptance,
                "ears_clauses": r.ears_clauses,
                "scenarios": r.scenarios,
                "clarifications": r.clarifications,
                "decision": r.decision,
                "revision_sha256": _requirement_revision_sha256(r),
            }
            for r in revisions
        ],
        "tasks": [
            TaskView.model_validate(
                {
                    "id": t.id,
                    "demand_id": t.demand_id,
                    "title": t.title,
                    "owner_role": t.owner_role,
                    "status": t.status,
                    "priority": t.priority,
                    "path_scopes": t.path_scopes,
                    "acceptance": t.acceptance,
                    "risk": t.risk,
                    "state_version": t.state_version,
                    "dependencies": by_task.get(t.id, []),
                    "blocked_reason": blocked_reason_by_task.get(t.id),
                    "runs": runs_by_task.get(t.id, []),
                }
            )
            for t in tasks
        ],
    }


@router.get("/{demand_id}/runs/{run_id}/artifacts/{artifact_id}")
def get_run_artifact(
    demand_id: str,
    run_id: str,
    artifact_id: str,
    session: Session = Depends(get_db),
) -> Response:
    run = session.get(AgentRun, run_id)
    artifact = session.get(Artifact, artifact_id)
    if run is None or artifact is None:
        raise HTTPException(status_code=404, detail={"code": "RUN_ARTIFACT_NOT_FOUND"})
    task = session.get(Task, run.task_id)
    if (
        task is None
        or task.demand_id != demand_id
        or artifact.subject_type != "run"
        or artifact.subject_id != run.id
    ):
        raise HTTPException(status_code=404, detail={"code": "RUN_ARTIFACT_NOT_FOUND"})
    relative = Path(artifact.relative_path)
    root = Path(os.getenv("RUNTIME_DIR", ".runtime")).resolve()
    prefix = Path("artifacts") / "run" / run.id
    if relative.is_absolute() or relative.parts[:3] != prefix.parts:
        raise HTTPException(status_code=404, detail={"code": "RUN_ARTIFACT_NOT_FOUND"})
    try:
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise OSError
        content = target.read_bytes()
    except OSError:
        raise HTTPException(status_code=404, detail={"code": "RUN_ARTIFACT_NOT_FOUND"}) from None
    if len(content) != artifact.size_bytes or len(content) > 5_000_000:
        raise HTTPException(status_code=409, detail={"code": "RUN_ARTIFACT_SIZE_MISMATCH"})
    digest = hashlib.sha256(content).hexdigest()
    if not re.fullmatch(r"[a-f0-9]{64}", artifact.sha256) or digest != artifact.sha256:
        raise HTTPException(status_code=409, detail={"code": "RUN_ARTIFACT_DIGEST_MISMATCH"})
    media_type = (
        artifact.media_type
        if re.fullmatch(r"[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+", artifact.media_type)
        else "application/octet-stream"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "inline",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
            "X-Artifact-SHA256": digest,
        },
    )


@router.post("/{demand_id}/run-fake")
def run_fake(demand_id: str, session: Session = Depends(get_db)) -> dict:
    if session.get(Demand, demand_id) is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    completed = run_fake_demand(session, demand_id)
    session.commit()
    return {
        "demand_id": demand_id,
        "reviewed_task_ids": completed,
        "model_called": False,
        "human_review_required": True,
    }


@router.post("/{demand_id}/tasks", response_model=TaskView, status_code=201)
def create_task(
    demand_id: str, payload: TaskCreate, session: Session = Depends(get_db)
) -> TaskView:
    demand = session.get(Demand, demand_id)
    if demand is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    if payload.execution_spec:
        from task_engine.execution import ExecutionError, validate_execution_spec

        try:
            validate_execution_spec(payload.execution_spec)
        except ExecutionError as exc:
            raise HTTPException(status_code=422, detail={"code": str(exc)}) from None
    task = Task(
        demand_id=demand_id,
        title=payload.title,
        owner_role=payload.owner_role,
        priority=payload.priority,
        path_scopes=payload.path_scopes,
        acceptance=payload.acceptance,
        risk=payload.risk,
        execution_spec=payload.execution_spec,
    )
    session.add(task)
    session.flush()
    known = session.scalars(select(Task.id).where(Task.demand_id == demand_id)).all()
    try:
        if payload.dependencies:
            add_dependencies(
                session, known, [(task.id, dependency) for dependency in payload.dependencies]
            )
        session.add(
            AuditRecord(
                subject_type="task",
                subject_id=task.id,
                action="task.created",
                actor="operator",
                details={
                    "demand_id": demand_id,
                    "dependencies": sorted(payload.dependencies),
                },
                evidence_hashes=[],
            )
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail={"code": str(exc)}) from None
    return TaskView(
        id=task.id,
        demand_id=task.demand_id,
        title=task.title,
        owner_role=task.owner_role,
        status=task.status,
        priority=task.priority,
        path_scopes=task.path_scopes,
        acceptance=task.acceptance,
        risk=task.risk,
        state_version=task.state_version,
        dependencies=payload.dependencies,
    )


@tasks_router.post("/{task_id}/transition", response_model=TaskView)
def transition_task(
    task_id: str, payload: TaskTransition, session: Session = Depends(get_db)
) -> TaskView:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND"})
    try:
        apply_transition(
            session,
            task,
            entity_type="task",
            new_state=payload.new_state,
            expected_version=payload.expected_version,
            actor="operator",
            reason=payload.reason,
            idempotency_key=payload.idempotency_key,
        )
        session.commit()
    except TransitionError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail={"code": exc.code}) from None
    deps = session.scalars(
        select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task_id)
    ).all()
    return TaskView(
        id=task.id,
        demand_id=task.demand_id,
        title=task.title,
        owner_role=task.owner_role,
        status=task.status,
        priority=task.priority,
        path_scopes=task.path_scopes,
        acceptance=task.acceptance,
        risk=task.risk,
        state_version=task.state_version,
        dependencies=list(deps),
    )


@tasks_router.get("", response_model=list[TaskView])
def list_tasks(
    status: str | None = Query(
        default=None,
        pattern=r"^(proposed|ready|leased|running|review|done|failed|blocked|retry_wait|cancelled)$",
    ),
    demand_id: str | None = Query(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$"),
    session: Session = Depends(get_db),
) -> list[TaskView]:
    query = select(Task)
    if status:
        query = query.where(Task.status == status)
    if demand_id:
        query = query.where(Task.demand_id == demand_id)
    tasks = session.scalars(
        query.order_by(Task.priority.desc(), Task.created_at, Task.id).limit(500)
    ).all()
    ids = [task.id for task in tasks]
    deps = (
        session.scalars(select(TaskDependency).where(TaskDependency.task_id.in_(ids))).all()
        if ids
        else []
    )
    by_task: dict[str, list[str]] = {}
    for dep in deps:
        by_task.setdefault(dep.task_id, []).append(dep.depends_on_id)
    return [
        TaskView(
            id=task.id,
            demand_id=task.demand_id,
            title=task.title,
            owner_role=task.owner_role,
            status=task.status,
            priority=task.priority,
            path_scopes=task.path_scopes,
            acceptance=task.acceptance,
            risk=task.risk,
            state_version=task.state_version,
            dependencies=by_task.get(task.id, []),
        )
        for task in tasks
    ]
