from __future__ import annotations

from datetime import UTC, datetime

from shared_contracts.db import Base
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

user_tags = Table(
    "user_tags",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_tags_normalized_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(96), nullable=False)
    users: Mapped[list[User]] = relationship(secondary=user_tags, back_populates="tags")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("normalized_email", name="uq_users_normalized_email"),
        UniqueConstraint("normalized_username", name="uq_users_normalized_username"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_users_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_username: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    normalized_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    tags: Mapped[list[Tag]] = relationship(secondary=user_tags, back_populates="users")
