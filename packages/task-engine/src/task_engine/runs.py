"""Validated persistence helpers for run provenance and gate evidence."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from task_engine.execution import PROFILE_GATES, assert_task_authorized
from task_engine.models import AgentRun, Artifact, GateEvidence, RequirementRevision, Task

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_GIT_SHA = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")


class RunProvenanceError(ValueError):
    pass


def create_run(
    session: Session,
    *,
    task_id: str,
    attempt: int,
    model_id: str,
    model_digest: str | None,
    prompt_hash: str,
    context_hash: str,
    skill_hash: str,
    requirement_revision_id: str,
    base_git_sha: str,
    executor_kind: str = "local_model",
) -> AgentRun:
    task = session.get(Task, task_id)
    revision = session.get(RequirementRevision, requirement_revision_id)
    if task is None or revision is None or revision.demand_id != task.demand_id:
        raise RunProvenanceError("RUN_CONTEXT_NOT_FOUND")
    if (
        attempt < 1
        or not model_id.strip()
        or executor_kind not in {"local_model", "assisted_patch"}
        or (executor_kind == "local_model" and (not model_digest or not model_digest.strip()))
        or (executor_kind == "assisted_patch" and model_digest is not None)
    ):
        raise RunProvenanceError("RUN_IDENTITY_INVALID")
    if not all(_SHA256.fullmatch(value) for value in (prompt_hash, context_hash, skill_hash)):
        raise RunProvenanceError("RUN_HASH_INVALID")
    if not _GIT_SHA.fullmatch(base_git_sha):
        raise RunProvenanceError("BASE_GIT_SHA_INVALID")
    if session.scalar(
        select(AgentRun.id).where(AgentRun.task_id == task_id, AgentRun.attempt == attempt)
    ):
        raise RunProvenanceError("RUN_ATTEMPT_EXISTS")
    authorized_revision, _ = assert_task_authorized(session, task)
    if authorized_revision.id != revision.id:
        raise RunProvenanceError("RUN_REQUIREMENT_STALE")
    if base_git_sha != task.execution_spec["base_git_sha"]:
        raise RunProvenanceError("RUN_BASE_NOT_APPROVED")
    if executor_kind != task.execution_spec.get("executor", "local_model"):
        raise RunProvenanceError("RUN_EXECUTOR_NOT_APPROVED")
    run = AgentRun(
        task_id=task_id,
        attempt=attempt,
        model_id=model_id.strip(),
        model_digest=model_digest.strip() if model_digest else None,
        executor_kind=executor_kind,
        prompt_hash=prompt_hash,
        context_hash=context_hash,
        skill_hash=skill_hash,
        requirement_revision_id=requirement_revision_id,
        base_git_sha=base_git_sha,
        status="running",
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:
        raise RunProvenanceError("RUN_ATTEMPT_EXISTS") from exc
    return run


def record_gate(
    session: Session,
    *,
    run_id: str,
    check_name: str,
    status: str,
    git_sha: str,
    tree_hash: str,
    suite_hash: str,
    tool_hash: str,
    config_hash: str,
    artifact_sha256: str,
) -> GateEvidence:
    run = session.get(AgentRun, run_id)
    if run is None:
        raise RunProvenanceError("RUN_NOT_FOUND")
    if status not in {"pass", "fail", "error", "skipped"} or not check_name.strip():
        raise RunProvenanceError("GATE_RESULT_INVALID")
    if not _GIT_SHA.fullmatch(git_sha) or git_sha != run.result_git_sha:
        raise RunProvenanceError("GATE_SHA_MISMATCH")
    if run.tree_hash != tree_hash:
        raise RunProvenanceError("GATE_TREE_MISMATCH")
    if not all(
        _SHA256.fullmatch(value) for value in (suite_hash, tool_hash, config_hash, artifact_sha256)
    ):
        raise RunProvenanceError("GATE_HASH_INVALID")
    evidence = GateEvidence(
        run_id=run.id,
        task_id=run.task_id,
        attempt=run.attempt,
        check_name=check_name.strip(),
        status=status,
        git_sha=git_sha,
        tree_hash=tree_hash,
        suite_hash=suite_hash,
        tool_hash=tool_hash,
        config_hash=config_hash,
        artifact_sha256=artifact_sha256,
        created_at=datetime.now(UTC),
    )
    session.add(evidence)
    try:
        session.flush()
    except IntegrityError as exc:
        raise RunProvenanceError("GATE_DUPLICATE") from exc
    return evidence


def assert_completion_evidence(session: Session, task: Task) -> AgentRun:
    result = task.result or {}
    run = session.get(AgentRun, result.get("run_id", ""))
    if (
        run is None
        or run.task_id != task.id
        or run.status != "completed"
        or run.attempt != result.get("attempt")
        or not run.result_git_sha
        or not run.tree_hash
        or result.get("result_sha") != run.result_git_sha
        or result.get("reviewed_sha") != run.result_git_sha
        or result.get("review_status") != "approved"
        or not result.get("review_model")
        or result["review_model"] == run.model_id
    ):
        raise RunProvenanceError("TASK_COMPLETION_EVIDENCE_REQUIRED")
    revision, _ = assert_task_authorized(session, task)
    if run.requirement_revision_id != revision.id:
        raise RunProvenanceError("RUN_REQUIREMENT_STALE")
    latest_attempt = session.scalar(
        select(AgentRun.attempt)
        .where(AgentRun.task_id == task.id)
        .order_by(AgentRun.attempt.desc())
        .limit(1)
    )
    if latest_attempt != run.attempt:
        raise RunProvenanceError("TASK_COMPLETION_ATTEMPT_STALE")
    gates = session.scalars(select(GateEvidence).where(GateEvidence.run_id == run.id)).all()
    required = set(PROFILE_GATES[task.execution_spec["profile"]])
    if not required.issubset({gate.check_name for gate in gates}) or any(
        gate.status != "pass"
        or gate.task_id != task.id
        or gate.attempt != run.attempt
        or gate.git_sha != run.result_git_sha
        or gate.tree_hash != run.tree_hash
        for gate in gates
    ):
        raise RunProvenanceError("TASK_COMPLETION_GATES_REQUIRED")
    artifacts = session.scalars(
        select(Artifact).where(
            Artifact.subject_type == "run",
            Artifact.subject_id == run.id,
        )
    ).all()
    hashes = {artifact.sha256 for artifact in artifacts}
    if result.get("review_artifact_sha256") not in hashes or any(
        gate.artifact_sha256 not in hashes for gate in gates
    ):
        raise RunProvenanceError("TASK_COMPLETION_ARTIFACTS_REQUIRED")
    return run
