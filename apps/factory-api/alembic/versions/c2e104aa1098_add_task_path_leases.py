"""Reserve overlapping task paths during active leases."""

import sqlalchemy as sa
from alembic import op

revision = "c2e104aa1098"
down_revision = "b4a2d8e61c09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_path_leases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "scope", name="uq_task_path_lease_scope"),
    )
    op.create_index("ix_task_path_leases_expiry", "task_path_leases", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_task_path_leases_expiry", table_name="task_path_leases")
    op.drop_table("task_path_leases")
