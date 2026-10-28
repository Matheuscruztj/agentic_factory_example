"""Immutable execution plans and server-side authorization at effect boundaries."""

from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from task_engine.models import (
    ApprovalRequest,
    Demand,
    EventOutbox,
    RequirementRevision,
    Task,
    TaskDependency,
)

PROFILE_GATES = {
    "python-fixture": ("python-tests",),
    "registry-backend": ("python-tests",),
    "registry-frontend": ("frontend-build", "browser-e2e"),
    "registry-frontend-build": ("frontend-build",),
    "registry-fullstack": ("python-tests", "frontend-build", "browser-e2e"),
}


class ExecutionError(ValueError):
    pass


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def validate_execution_spec(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - {
        "base_git_sha",
        "profile",
        "context_paths",
        "max_attempts",
        "max_output_tokens",
        "sandbox_pids_limit",
        "fixture_path",
        "executor",
        "patch_artifact",
        "patch_sha256",
    }:
        raise ExecutionError("EXECUTION_SPEC_INVALID")
    if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", str(value.get("base_git_sha", ""))):
        raise ExecutionError("EXECUTION_BASE_REQUIRED")
    if value.get("profile") not in PROFILE_GATES:
        raise ExecutionError("EXECUTION_PROFILE_INVALID")
    if value.get("executor", "local_model") not in {"local_model", "assisted_patch"}:
        raise ExecutionError("EXECUTION_KIND_INVALID")
    if value.get("executor") == "assisted_patch":
        artifact = value.get("patch_artifact", "")
        if (
            not isinstance(artifact, str)
            or not artifact.startswith("artifacts/approved-patches/")
            or not artifact.endswith(".json")
            or ".." in artifact.split("/")
            or "\\" in artifact
        ):
            raise ExecutionError("ASSISTED_PATCH_PATH_INVALID")
        if not re.fullmatch(r"[a-f0-9]{64}", str(value.get("patch_sha256", ""))):
            raise ExecutionError("ASSISTED_PATCH_HASH_REQUIRED")
    paths = value.get("context_paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= 16:
        raise ExecutionError("EXECUTION_CONTEXT_REQUIRED")
    for path in [*paths, *([value["fixture_path"]] if "fixture_path" in value else [])]:
        if (
            not isinstance(path, str)
            or not path
            or path.startswith("/")
            or "\\" in path
            or "\x00" in path
            or any(part in {"", ".", ".."} for part in path.split("/"))
        ):
            raise ExecutionError("EXECUTION_PATH_INVALID")
    for key, default, upper in (("max_attempts", 2, 5), ("max_output_tokens", 4096, 8192)):
        number = value.get(key, default)
        if type(number) is not int or not 1 <= number <= upper:
            raise ExecutionError("EXECUTION_BUDGET_INVALID")
    pids_limit = value.get("sandbox_pids_limit", 128)
    if type(pids_limit) is not int or not 64 <= pids_limit <= 512:
        raise ExecutionError("EXECUTION_BUDGET_INVALID")
    if value["profile"] == "python-fixture" and not value.get("fixture_path"):
        raise ExecutionError("EXECUTION_FIXTURE_REQUIRED")
    return dict(value)


def execution_plan(session: Session, demand_id: str) -> dict:
    demand = session.get(Demand, demand_id)
    if demand is None:
        raise ExecutionError("EXECUTION_DEMAND_NOT_FOUND")
    revision = session.scalar(
        select(RequirementRevision)
        .where(RequirementRevision.demand_id == demand_id)
        .order_by(RequirementRevision.version.desc())
        .limit(1)
    )
    if revision is None or revision.decision != "approved":
        raise ExecutionError("EXECUTION_REQUIREMENT_NOT_APPROVED")
    tasks = session.scalars(select(Task).where(Task.demand_id == demand_id).order_by(Task.id)).all()
    task_ids = [task.id for task in tasks]
    edges = (
        session.execute(
            select(TaskDependency.task_id, TaskDependency.depends_on_id)
            .where(TaskDependency.task_id.in_(task_ids))
            .order_by(TaskDependency.task_id, TaskDependency.depends_on_id)
        ).all()
        if task_ids
        else []
    )
    plan = {
        "demand_id": demand.id,
        "demand_version": demand.version,
        "repository_id": demand.repository_id,
        "requirement": {
            key: getattr(revision, key)
            for key in (
                "id",
                "version",
                "content",
                "acceptance",
                "ears_clauses",
                "scenarios",
                "clarifications",
                "decision",
            )
        },
        "tasks": [
            {
                key: getattr(task, key)
                for key in (
                    "id",
                    "title",
                    "owner_role",
                    "path_scopes",
                    "acceptance",
                    "risk",
                    "execution_spec",
                )
            }
            for task in tasks
        ],
        "dependencies": [list(edge) for edge in edges],
    }

    return json.loads(json.dumps(plan, ensure_ascii=False))


def assert_task_authorized(session: Session, task: Task) -> tuple[RequirementRevision, str]:
    """Runtime states can change; any requirement/plan change revokes the grant."""
    plan = execution_plan(session, task.demand_id)
    validate_execution_spec(task.execution_spec)
    if not task.path_scopes or not task.acceptance:
        raise ExecutionError("EXECUTION_SCOPE_REQUIRED")
    grants = session.scalars(
        select(ApprovalRequest).where(
            ApprovalRequest.entity_type.in_(("demand", "task")),
            ApprovalRequest.entity_id.in_((task.id, task.demand_id)),
            ApprovalRequest.status == "approved",
        )
    ).all()
    for grant in grants:
        if not grant.decision_by or grant.requested_by == grant.decision_by or not grant.decided_at:
            continue
        event = session.scalar(
            select(EventOutbox).where(
                EventOutbox.event_id == f"approval-decided:{grant.id}",
                EventOutbox.event_type == "human.approval.decided",
            )
        )
        if event is not None and (
            event.payload.get("decision") == "approved"
            and event.payload.get("payload_hash") == grant.payload_hash
            and event.payload.get("execution_plan") == plan
        ):
            revision = session.get(RequirementRevision, plan["requirement"]["id"])
            assert revision is not None
            return revision, grant.id
    raise ExecutionError("EXECUTION_PLAN_APPROVAL_REQUIRED")
