from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable


class DagValidationError(ValueError):
    pass


def validate_dag(task_ids: Iterable[str], edges: Iterable[tuple[str, str]]) -> list[str]:
    """Validate (task_id, dependency_id) edges and return a topological order."""
    ids = set(task_ids)
    outgoing: dict[str, set[str]] = defaultdict(set)
    indegree = dict.fromkeys(ids, 0)
    for task_id, dependency_id in edges:
        if task_id not in ids or dependency_id not in ids:
            raise DagValidationError("DEPENDENCY_TASK_NOT_FOUND")
        if task_id == dependency_id:
            raise DagValidationError("DEPENDENCY_SELF_REFERENCE")
        if task_id not in outgoing[dependency_id]:
            outgoing[dependency_id].add(task_id)
            indegree[task_id] += 1
    ready = deque(sorted(task_id for task_id, degree in indegree.items() if degree == 0))
    ordered: list[str] = []
    while ready:
        task_id = ready.popleft()
        ordered.append(task_id)
        for dependent in sorted(outgoing[task_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if len(ordered) != len(ids):
        raise DagValidationError("DEPENDENCY_CYCLE")
    return ordered


def is_ready(task_id: str, edges: Iterable[tuple[str, str]], task_states: dict[str, str]) -> bool:
    relevant = [(task, dependency) for task, dependency in edges if task == task_id]
    if task_id not in task_states:
        raise DagValidationError("TASK_NOT_FOUND")
    return task_states[task_id] in {"proposed", "ready"} and all(
        task_states.get(dependency) == "done" for _, dependency in relevant
    )
