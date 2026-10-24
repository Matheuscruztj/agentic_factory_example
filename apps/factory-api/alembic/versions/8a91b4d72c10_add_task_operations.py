"""Add leases, outbox/inbox, audit trail, artifacts, and snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "8a91b4d72c10"
down_revision = "070399e07827"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(
            sa.Column("fencing_token", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("lease_owner", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("result", sa.JSON(), nullable=True))
    op.create_table(
        "event_outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(160), nullable=False, unique=True),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_outbox_pending", "event_outbox", ["published_at", "created_at"])
    op.create_table(
        "event_inbox",
        sa.Column("event_id", sa.String(160), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )
    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("evidence_hashes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_audit_subject", "audit_records", ["subject_type", "subject_id", "created_at"]
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("relative_path", sa.String(500), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "entity_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_id", "version", name="uq_snapshot_version"),
    )
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("requested_by", sa.String(120), nullable=False),
        sa.Column("decision_by", sa.String(120), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approvals_status", "approval_requests", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_approvals_status", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_table("entity_snapshots")
    op.drop_table("artifacts")
    op.drop_index("ix_audit_subject", table_name="audit_records")
    op.drop_table("audit_records")
    op.drop_table("event_inbox")
    op.drop_index("ix_outbox_pending", table_name="event_outbox")
    op.drop_table("event_outbox")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_column("result")
        batch.drop_column("lease_expires_at")
        batch.drop_column("lease_owner")
        batch.drop_column("fencing_token")
