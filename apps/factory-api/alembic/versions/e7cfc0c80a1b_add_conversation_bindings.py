"""Add persistent bindings between OpenBot threads and factory entities."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e7cfc0c80a1b"
down_revision = "8a91b4d72c10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_bindings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=16), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("persona", sa.String(length=32), nullable=False),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("snapshot_sha", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('demand', 'task')",
            name="ck_conversation_binding_entity_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", name="uq_conversation_bindings_thread"),
    )
    op.create_index(
        "ix_conversation_bindings_entity",
        "conversation_bindings",
        ["entity_type", "entity_id", "persona"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_bindings_entity", table_name="conversation_bindings")
    op.drop_table("conversation_bindings")
