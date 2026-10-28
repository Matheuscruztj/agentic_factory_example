from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from shared_contracts.db import Base
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Demand(Base):
    __tablename__ = "demands"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_demands_source_external"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    demand_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    risk: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    repository_id: Mapped[str] = mapped_column(String(80), nullable=False, default="self")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class ConversationBinding(Base):
    __tablename__ = "conversation_bindings"
    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_conversation_bindings_thread"),
        Index("ix_conversation_bindings_entity", "entity_type", "entity_id", "persona"),
        CheckConstraint(
            "entity_type IN ('demand', 'task')",
            name="ck_conversation_binding_entity_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    persona: Mapped[str] = mapped_column(String(32), nullable=False)
    participants: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    snapshot_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ConversationTaskProposal(Base):
    """A change intent captured from an agent conversation; never executable by itself."""

    __tablename__ = "conversation_task_proposals"
    __table_args__ = (
        UniqueConstraint("thread_id", "message_id", name="uq_conversation_proposal_message"),
        Index("ix_conversation_proposals_demand", "demand_id", "status", "created_at"),
        CheckConstraint(
            "status IN ('pending_review', 'accepted', 'rejected')",
            name="ck_conversation_proposal_status",
        ),
        CheckConstraint("executable = false", name="ck_conversation_proposal_inert"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    demand_id: Mapped[str] = mapped_column(
        ForeignKey("demands.id", ondelete="CASCADE"), nullable=False
    )
    persona: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    path_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    acceptance: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    executable: Mapped[bool] = mapped_column(nullable=False, default=False)
    requires_human_review: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_task_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class RequirementRevision(Base):
    __tablename__ = "requirement_revisions"
    __table_args__ = (
        UniqueConstraint("demand_id", "version", name="uq_requirement_demand_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    demand_id: Mapped[str] = mapped_column(
        ForeignKey("demands.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ears_clauses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    scenarios: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    clarifications: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority BETWEEN 0 AND 100", name="ck_tasks_priority"),
        Index("ix_tasks_demand_status", "demand_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    demand_id: Mapped[str] = mapped_column(
        ForeignKey("demands.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="proposed")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    path_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    acceptance: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risk: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    expected_demand_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    execution_spec: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (UniqueConstraint("task_id", "depends_on_id", name="uq_task_dependency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    depends_on_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )


class TaskPathLease(Base):
    """Path scopes reserved by an active task lease."""

    __tablename__ = "task_path_leases"
    __table_args__ = (
        UniqueConstraint("task_id", "scope", name="uq_task_path_lease_scope"),
        Index("ix_task_path_leases_expiry", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TransitionEvent(Base):
    __tablename__ = "transition_events"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "idempotency_key", name="uq_transition_idempotency"
        ),
        Index("ix_transition_entity", "entity_type", "entity_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EventOutbox(Base):
    __tablename__ = "event_outbox"
    __table_args__ = (Index("ix_outbox_pending", "published_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EventInbox(Base):
    __tablename__ = "event_inbox"

    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class RetryQueueEntry(Base):
    """Durable retry/dead-letter state, separate from publishable outbox events."""

    __tablename__ = "retry_queue"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "operation_key", "failed_attempt", name="uq_retry_operation_attempt"
        ),
        Index("ix_retry_due", "status", "available_at"),
        CheckConstraint(
            "status IN ('retry_wait', 'dead_letter', 'completed')", name="ck_retry_status"
        ),
        CheckConstraint("failed_attempt >= 1 AND max_attempts >= 1", name="ck_retry_attempts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(200), nullable=False)
    failed_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_by: Mapped[str | None] = mapped_column(String(120))
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunFeedback(Base):
    """Immutable, operator-attributed feedback tied to one execution run."""

    __tablename__ = "run_feedback"
    __table_args__ = (
        UniqueConstraint("run_id", "reviewer_sub", name="uq_run_feedback_reviewer"),
        CheckConstraint("decision IN ('approve', 'reject')", name="ck_run_feedback_decision"),
        Index("ix_run_feedback_task_created", "task_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    demand_id: Mapped[str | None] = mapped_column(ForeignKey("demands.id", ondelete="SET NULL"))
    reviewer_sub: Mapped[str] = mapped_column(String(120), nullable=False)
    decision: Mapped[str] = mapped_column(String(12), nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(48))
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(120), nullable=False)
    requirement_version: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AgentRun(Base):
    """Authoritative provenance record for one task execution attempt."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt", name="uq_agent_run_task_attempt"),
        CheckConstraint("attempt >= 1", name="ck_agent_run_attempt"),
        Index("ix_agent_runs_task_created", "task_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[str] = mapped_column(String(120), nullable=False)
    model_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    executor_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="local_model")
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requirement_revision_id: Mapped[str] = mapped_column(
        ForeignKey("requirement_revisions.id"), nullable=False
    )
    base_git_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    result_git_sha: Mapped[str | None] = mapped_column(String(64))
    tree_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GateEvidence(Base):
    """Gate result tied to the exact run snapshot and verified artifact."""

    __tablename__ = "gate_evidence"
    __table_args__ = (
        UniqueConstraint("run_id", "check_name", name="uq_gate_run_check"),
        Index("ix_gate_evidence_task", "task_id", "attempt"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    check_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    git_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    tree_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    suite_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PromptRelease(Base):
    """Immutable approval/activation event for a content-addressed prompt."""

    __tablename__ = "prompt_releases"
    __table_args__ = (
        Index("ix_prompt_release_active", "active", "created_at"),
        CheckConstraint("action IN ('promote', 'rollback')", name="ck_prompt_release_action"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_version: Mapped[str | None] = mapped_column(String(120))
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    experiment_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AuditRecord(Base):
    __tablename__ = "audit_records"
    __table_args__ = (Index("ix_audit_subject", "subject_type", "subject_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    evidence_hashes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(
        String(120), nullable=False, default="application/octet-stream"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EntitySnapshot(Base):
    __tablename__ = "entity_snapshots"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "version", name="uq_snapshot_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (Index("ix_approvals_status", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entity_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    requested_by: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_by: Mapped[str | None] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
