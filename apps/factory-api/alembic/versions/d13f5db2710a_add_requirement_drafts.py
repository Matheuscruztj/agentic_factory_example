"""Persist EARS clauses and review scenarios for each requirement revision."""

import sqlalchemy as sa
from alembic import op

revision = "d13f5db2710a"
down_revision = "c2e104aa1098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("requirement_revisions") as batch:
        batch.add_column(
            sa.Column("ears_clauses", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch.add_column(
            sa.Column("scenarios", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch.add_column(
            sa.Column("clarifications", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )


def downgrade() -> None:
    with op.batch_alter_table("requirement_revisions") as batch:
        batch.drop_column("clarifications")
        batch.drop_column("scenarios")
        batch.drop_column("ears_clauses")
