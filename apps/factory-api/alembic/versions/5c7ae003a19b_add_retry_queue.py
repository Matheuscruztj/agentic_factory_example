"""Add persistent workflow retry and dead-letter queue."""

import sqlalchemy as sa
from alembic import op

revision = "5c7ae003a19b"
down_revision = "3b1a8cb7fd21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retry_queue",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("operation_key", sa.String(length=200), nullable=False),
        sa.Column("failed_attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("failure_kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('retry_wait', 'dead_letter', 'completed')", name="ck_retry_status"
        ),
        sa.CheckConstraint(
            "failed_attempt >= 1 AND max_attempts >= 1", name="ck_retry_attempts"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id", "operation_key", "failed_attempt", name="uq_retry_operation_attempt"
        ),
    )
    op.create_index("ix_retry_due", "retry_queue", ["status", "available_at"])


def downgrade() -> None:
    op.drop_index("ix_retry_due", table_name="retry_queue")
    op.drop_table("retry_queue")
