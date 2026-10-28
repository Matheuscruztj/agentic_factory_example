"""Persist OpenBot thread identity separately from demand/task context."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session
from task_engine.models import ConversationBinding, Demand, Task


class BindingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BoundEntity:
    entity_type: str
    entity_id: str
    version: int


def resolve_reference(session: Session, reference: str) -> BoundEntity:
    demand_ref = re.fullmatch(r"DEMAND-([0-9a-f-]{36})", reference, re.IGNORECASE)
    if demand_ref:
        row = session.get(Demand, demand_ref.group(1))
        if row is None:
            raise BindingError("DEMAND_NOT_FOUND")
        return BoundEntity("demand", row.id, row.version)
    issue = re.fullmatch(r"ISSUE-([1-9][0-9]*)", reference, re.IGNORECASE)
    if issue:
        row = session.scalar(
            select(Demand).where(
                Demand.source == "github",
                Demand.external_id == issue.group(1),
            )
        )
        if row is None:
            raise BindingError("ISSUE_NOT_FOUND")
        return BoundEntity("demand", row.id, row.version)
    task = re.fullmatch(r"TASK-([0-9a-f-]{36})", reference, re.IGNORECASE)
    if task:
        row = session.get(Task, task.group(1))
        if row is None:
            raise BindingError("TASK_NOT_FOUND")
        return BoundEntity("task", row.id, row.state_version)
    raise BindingError("UNSUPPORTED_ENTITY_REFERENCE")


def bind_thread(
    session: Session,
    *,
    thread_id: str,
    reference: str,
    persona: str,
    participants: list[str],
    snapshot_sha: str,
    policy_id: str,
) -> ConversationBinding:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", thread_id):
        raise BindingError("INVALID_THREAD_ID")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", persona):
        raise BindingError("INVALID_PERSONA")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", snapshot_sha):
        raise BindingError("INVALID_SNAPSHOT_SHA")
    if (
        not isinstance(policy_id, str)
        or not policy_id.strip()
        or len(policy_id) > 120
        or not participants
        or len(participants) > 16
        or any(
            not isinstance(item, str) or not item.strip() or len(item) > 120
            for item in participants
        )
    ):
        raise BindingError("BINDING_POLICY_AND_PARTICIPANTS_REQUIRED")
    entity = resolve_reference(session, reference)
    current = session.scalar(
        select(ConversationBinding).where(ConversationBinding.thread_id == thread_id)
    )
    if current is not None:
        same_binding = (
            current.entity_type == entity.entity_type
            and current.entity_id == entity.entity_id
            and current.persona == persona
            and current.policy_id == policy_id
        )
        if not same_binding:
            raise BindingError("THREAD_ALREADY_BOUND_TO_DIFFERENT_CONTEXT")
        return current
    binding = ConversationBinding(
        thread_id=thread_id,
        entity_type=entity.entity_type,
        entity_id=entity.entity_id,
        persona=persona,
        participants=sorted(set(participants)),
        snapshot_sha=snapshot_sha,
        policy_id=policy_id,
    )
    session.add(binding)
    session.flush()
    return binding


def load_bound_entity(session: Session, binding: ConversationBinding):
    """Resolve only the exact entity stored on this thread; never infer from chat text."""
    model = Demand if binding.entity_type == "demand" else Task
    entity = session.get(model, binding.entity_id)
    if entity is None:
        raise BindingError("BOUND_ENTITY_NOT_FOUND")
    return entity
