"""Add expiring ownership claims to retry workers."""

import sqlalchemy as sa
from alembic import op

revision = "6ac47e2110e9"
down_revision = "4f3a9e8721cc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("retry_queue", sa.Column("claimed_by", sa.String(length=120), nullable=True))
    op.add_column(
        "retry_queue", sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("retry_queue", "claim_expires_at")
    op.drop_column("retry_queue", "claimed_by")
