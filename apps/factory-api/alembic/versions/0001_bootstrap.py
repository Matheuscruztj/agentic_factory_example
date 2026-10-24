"""Initial database revision; creates the shared metadata schema."""

revision = "0001_bootstrap"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Domain tables are added by later tasks. The revision establishes the durable migration chain.
    pass


def downgrade() -> None:
    pass
