"""Store scoped proposal data and idempotent accepted task linkage."""

import sqlalchemy as sa
from alembic import op

revision = "4f3a9e8721cc"
down_revision = "5c7ae003a19b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_task_proposals",
        sa.Column("path_scopes", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "conversation_task_proposals",
        sa.Column("acceptance", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "conversation_task_proposals", sa.Column("created_task_id", sa.String(length=36))
    )


def downgrade() -> None:
    op.drop_column("conversation_task_proposals", "created_task_id")
    op.drop_column("conversation_task_proposals", "acceptance")
    op.drop_column("conversation_task_proposals", "path_scopes")
