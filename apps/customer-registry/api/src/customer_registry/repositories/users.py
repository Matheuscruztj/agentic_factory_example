from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from customer_registry.models import User


class DuplicateUserField(ValueError):
    def __init__(self, field: str):
        self.field = field
        super().__init__(field)


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self, search: str | None = None, include_inactive: bool = False) -> list[User]:
        query = select(User)
        if not include_inactive:
            query = query.where(User.status == "active")
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    User.name.ilike(pattern),
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        return list(self.session.scalars(query.order_by(User.name, User.created_at)))

    def get(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    def create(self, *, username: str, name: str, email: str) -> User:
        user = User(
            id=str(uuid4()),
            username=username,
            normalized_username=username.casefold(),
            name=name,
            email=email,
            normalized_email=email.casefold(),
            status="active",
        )
        self.session.add(user)
        self._commit(user, username=username)
        return user

    def update(self, user: User, values: dict[str, str]) -> User:
        for key, value in values.items():
            setattr(user, key, value)
            if key == "username":
                user.normalized_username = value.casefold()
            elif key == "email":
                user.normalized_email = value.casefold()
        user.updated_at = datetime.now(UTC)
        self._commit(user, username=values.get("username"))
        return user

    def deactivate(self, user: User) -> None:
        user.status = "inactive"
        user.updated_at = datetime.now(UTC)
        self.session.commit()

    def _commit(self, user: User, *, username: str | None = None) -> None:
        try:
            self.session.commit()
            self.session.refresh(user)
        except IntegrityError as exc:
            self.session.rollback()
            message = str(exc.orig).lower()
            field = (
                "username" if "username" in message or "normalized_username" in message else "email"
            )
            raise DuplicateUserField(field) from None
