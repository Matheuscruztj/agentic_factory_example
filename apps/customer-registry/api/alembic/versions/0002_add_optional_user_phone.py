"""Add optional telephone to synthetic registry demo."""

import sqlalchemy as sa
from alembic import op

revision = "0002_add_optional_user_phone"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone")
