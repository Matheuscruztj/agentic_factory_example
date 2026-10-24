from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from task_engine.dependencies import add_dependencies
from task_engine.models import Demand, RequirementRevision, Task, TaskDependency
from task_engine.requirements import RequirementError, add_revision, create_demand
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


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    owner_role: str = Field(min_length=1, max_length=64)
    priority: int = Field(default=50, ge=0, le=100)
    path_scopes: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    risk: str = Field(default="normal", max_length=16)
    dependencies: list[str] = Field(default_factory=list)


class TaskTransition(BaseModel):
    new_state: str = Field(min_length=1, max_length=24)
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=160)


@router.post("", response_model=DemandView, status_code=201)
def create_demand_endpoint(payload: DemandCreate, session: Session = Depends(get_db)) -> DemandView:
    try:
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
        raise HTTPException(status_code=409, detail={"code": "DEMAND_ALREADY_EXISTS"}) from None


@router.get("", response_model=list[DemandView])
def list_demands(
    status: str | None = Query(default=None),
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
    return {
        "demand": DemandView.from_model(demand),
        "revisions": [
            {
                "id": r.id,
                "version": r.version,
                "content": r.content,
                "acceptance": r.acceptance,
                "decision": r.decision,
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
                }
            )
            for t in tasks
        ],
    }


@router.post("/{demand_id}/run-fake")
def run_fake(demand_id: str, session: Session = Depends(get_db)) -> dict:
    if session.get(Demand, demand_id) is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    completed = run_fake_demand(session, demand_id)
    session.commit()
    return {
        "demand_id": demand_id,
        "completed_task_ids": completed,
        "model_called": False,
        "approval_required": True,
    }


@router.post("/{demand_id}/tasks", response_model=TaskView, status_code=201)
def create_task(
    demand_id: str, payload: TaskCreate, session: Session = Depends(get_db)
) -> TaskView:
    demand = session.get(Demand, demand_id)
    if demand is None:
        raise HTTPException(status_code=404, detail={"code": "DEMAND_NOT_FOUND"})
    task = Task(
        demand_id=demand_id,
        title=payload.title,
        owner_role=payload.owner_role,
        priority=payload.priority,
        path_scopes=payload.path_scopes,
        acceptance=payload.acceptance,
        risk=payload.risk,
    )
    session.add(task)
    session.flush()
    known = session.scalars(select(Task.id).where(Task.demand_id == demand_id)).all()
    try:
        if payload.dependencies:
            add_dependencies(
                session, known, [(task.id, dependency) for dependency in payload.dependencies]
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
        dependencies=deps,
    )


@tasks_router.get("", response_model=list[TaskView])
def list_tasks(
    status: str | None = Query(default=None),
    demand_id: str | None = Query(default=None),
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
