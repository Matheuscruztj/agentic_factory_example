"""Allow Unicode casefold expansion without reducing the 32-character name limit."""

import sqlalchemy as sa
from alembic import op

revision = "0004_expand_tag_normalization"
down_revision = "0003_add_shared_tags"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tags") as batch:
        batch.alter_column(
            "normalized_name", existing_type=sa.String(32), type_=sa.String(96), nullable=False
        )


def downgrade():
    # Refuse to truncate or merge distinct normalized names during rollback.
    if (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM tags WHERE length(normalized_name) > 32"))
        .scalar()
    ):
        raise ValueError("TAG_NORMALIZATION_DOWNGRADE_WOULD_TRUNCATE")
    with op.batch_alter_table("tags") as batch:
        batch.alter_column(
            "normalized_name", existing_type=sa.String(96), type_=sa.String(32), nullable=False
        )
