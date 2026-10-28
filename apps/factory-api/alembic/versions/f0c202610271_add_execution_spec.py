"""Bind the concrete runner profile and baseline to the approved task plan."""

import sqlalchemy as sa
from alembic import op

revision = "f0c202610271"
down_revision = "d13f5db2710a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("execution_spec", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("tasks", "execution_spec")
