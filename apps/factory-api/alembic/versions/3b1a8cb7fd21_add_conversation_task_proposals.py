"""Persist inert TaskProposal records from agent conversations."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "3b1a8cb7fd21"
down_revision = "e7cfc0c80a1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_task_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("message_id", sa.String(length=128), nullable=False),
        sa.Column("demand_id", sa.String(length=36), nullable=False),
        sa.Column("persona", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("executable", sa.Boolean(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending_review', 'accepted', 'rejected')",
            name="ck_conversation_proposal_status",
        ),
        sa.CheckConstraint("executable = false", name="ck_conversation_proposal_inert"),
        sa.ForeignKeyConstraint(["demand_id"], ["demands.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", "message_id", name="uq_conversation_proposal_message"),
    )
    op.create_index(
        "ix_conversation_proposals_demand",
        "conversation_task_proposals",
        ["demand_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_proposals_demand", table_name="conversation_task_proposals")
    op.drop_table("conversation_task_proposals")
