"""Add shared customer tags and associations."""

import sqlalchemy as sa
from alembic import op

revision = "0003_add_shared_tags"
down_revision = "0002_add_optional_user_phone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("normalized_name", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("normalized_name", name="uq_tags_normalized_name"),
    )
    op.create_table(
        "user_tags",
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.String(length=36),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_tags")
    op.drop_table("tags")
