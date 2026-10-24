from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.dag import validate_dag
from task_engine.models import Task, TaskDependency


def add_dependencies(
    session: Session, task_ids: Iterable[str], edges: Iterable[tuple[str, str]]
) -> None:
    task_ids = list(task_ids)
    edges = list(edges)
    validate_dag(task_ids, edges)
    existing = set(session.scalars(select(Task.id).where(Task.id.in_(task_ids))))
    if existing != set(task_ids):
        raise ValueError("TASK_NOT_FOUND")
    for task_id, dependency_id in edges:
        session.add(TaskDependency(task_id=task_id, depends_on_id=dependency_id))
    session.flush()
