from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from customer_registry.models import Tag, User


class DuplicateUserField(ValueError):
    def __init__(self, field: str):
        self.field = field
        super().__init__(field)


class DuplicateTag(ValueError):
    pass


class InvalidTags(ValueError):
    pass


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(
        self, search: str | None = None, include_inactive: bool = False, tag_id: str | None = None
    ) -> list[User]:
        query = select(User).options(selectinload(User.tags))
        if not include_inactive:
            query = query.where(User.status == "active")
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    User.name.ilike(pattern),
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                    User.phone.ilike(pattern),
                )
            )
        if tag_id:
            query = query.join(User.tags).where(Tag.id == tag_id)
        return list(self.session.scalars(query.order_by(User.name, User.created_at)))

    def list_tags(self) -> list[Tag]:
        return list(self.session.scalars(select(Tag).order_by(func.lower(Tag.name), Tag.name)))

    def create_tag(self, name: str) -> Tag:
        normalized = name.strip().casefold()
        if self.session.scalar(select(Tag.id).where(Tag.normalized_name == normalized)):
            raise DuplicateTag from None
        tag = Tag(id=str(uuid4()), name=name.strip(), normalized_name=normalized)
        self.session.add(tag)
        try:
            self.session.commit()
            self.session.refresh(tag)
        except IntegrityError:
            self.session.rollback()
            raise DuplicateTag from None
        return tag

    def set_user_tags(self, user: User, tag_ids: list[str]) -> None:
        user.tags = self._resolve_tags(tag_ids)
        self.session.commit()
        self.session.refresh(user)

    def _resolve_tags(self, tag_ids: list[str]) -> list[Tag]:
        unique_ids = list(dict.fromkeys(tag_ids))
        if len(unique_ids) != len(tag_ids) or len(unique_ids) > 10:
            raise InvalidTags
        tags = (
            list(self.session.scalars(select(Tag).where(Tag.id.in_(unique_ids))))
            if unique_ids
            else []
        )
        if len(tags) != len(unique_ids):
            raise InvalidTags
        return tags

    def get(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    def create(
        self,
        *,
        username: str,
        name: str,
        email: str,
        phone: str | None = None,
        tag_ids: list[str] | None = None,
    ) -> User:
        user = User(
            id=str(uuid4()),
            username=username,
            normalized_username=username.casefold(),
            name=name,
            email=email,
            phone=phone,
            normalized_email=email.casefold(),
            status="active",
        )
        self.session.add(user)
        try:
            user.tags = self._resolve_tags(tag_ids or [])
            self._commit(user, username=username)
        except InvalidTags:
            self.session.rollback()
            raise
        return user

    def update(
        self, user: User, values: dict[str, str], *, tag_ids: list[str] | None = None
    ) -> User:
        for key, value in values.items():
            setattr(user, key, value)
            if key == "username":
                user.normalized_username = value.casefold()
            elif key == "email":
                user.normalized_email = value.casefold()
        user.updated_at = datetime.now(UTC)
        if tag_ids is not None:
            user.tags = self._resolve_tags(tag_ids)
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
