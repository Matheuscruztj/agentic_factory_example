"""Add authoritative agent runs and gate provenance."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9d12a7c41e30"
down_revision = "5a96d537ebaf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(120), nullable=False),
        sa.Column("model_digest", sa.String(128), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("skill_hash", sa.String(64), nullable=False),
        sa.Column(
            "requirement_revision_id",
            sa.String(36),
            sa.ForeignKey("requirement_revisions.id"),
            nullable=False,
        ),
        sa.Column("base_git_sha", sa.String(64), nullable=False),
        sa.Column("result_git_sha", sa.String(64)),
        sa.Column("tree_hash", sa.String(64)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("attempt >= 1", name="ck_agent_run_attempt"),
        sa.UniqueConstraint("task_id", "attempt", name="uq_agent_run_task_attempt"),
    )
    op.create_index("ix_agent_runs_task_created", "agent_runs", ["task_id", "started_at"])
    op.create_table(
        "gate_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("check_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("git_sha", sa.String(64), nullable=False),
        sa.Column("tree_hash", sa.String(64), nullable=False),
        sa.Column("suite_hash", sa.String(64), nullable=False),
        sa.Column("tool_hash", sa.String(64), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "check_name", name="uq_gate_run_check"),
    )
    op.create_index("ix_gate_evidence_task", "gate_evidence", ["task_id", "attempt"])
    with op.batch_alter_table("run_feedback") as batch:
        batch.create_foreign_key(
            "fk_run_feedback_run", "agent_runs", ["run_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("run_feedback") as batch:
        batch.drop_constraint("fk_run_feedback_run", type_="foreignkey")
    op.drop_index("ix_gate_evidence_task", table_name="gate_evidence")
    op.drop_table("gate_evidence")
    op.drop_index("ix_agent_runs_task_created", table_name="agent_runs")
    op.drop_table("agent_runs")
