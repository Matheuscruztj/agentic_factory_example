"""Distinguish authorized assisted patches from model inference without inventing a digest."""

import sqlalchemy as sa
from alembic import op

revision = "f1c202610272"
down_revision = "f0c202610271"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch:
        batch.add_column(
            sa.Column("executor_kind", sa.String(32), nullable=False, server_default="local_model")
        )
        batch.alter_column("model_digest", existing_type=sa.String(128), nullable=True)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text("SELECT count(*) FROM agent_runs WHERE model_digest IS NULL")
    ).scalar():
        raise RuntimeError("ASSISTED_PROVENANCE_CANNOT_BE_DISCARDED_BY_DOWNGRADE")
    with op.batch_alter_table("agent_runs") as batch:
        batch.alter_column("model_digest", existing_type=sa.String(128), nullable=False)
        batch.drop_column("executor_kind")
