"""Standalone local API for the customer registry."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from customer_registry.database import get_engine, initialize_sqlite, session_factory
from customer_registry.models import User
from customer_registry.repositories.users import (
    DuplicateTag,
    DuplicateUserField,
    InvalidTags,
    UserRepository,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_sqlite()
    yield


class UserInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$")
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=254)
    phone: str | None = Field(default=None, min_length=7, max_length=32, pattern=r"^\+?[0-9 ()-]+$")
    tag_ids: list[UUID] = Field(default_factory=list, max_length=10)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else None


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str | None = Field(
        default=None, min_length=3, max_length=32, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$"
    )
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, min_length=7, max_length=32, pattern=r"^\+?[0-9 ()-]+$")
    tag_ids: list[UUID] | None = Field(default=None, max_length=10)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class UserRead(BaseModel):
    id: UUID
    username: str
    name: str
    email: EmailStr
    phone: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    tags: list[TagRead] = Field(default_factory=list)


class TagRead(BaseModel):
    id: UUID
    name: str


class TagInput(BaseModel):
    name: str = Field(min_length=1, max_length=32)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("name must be text")
        value = value.strip()
        if not 1 <= len(value) <= 32:
            raise ValueError("name must contain 1 to 32 characters")
        return value


app = FastAPI(title="Customer Registry API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "REGISTRY_CORS_ORIGINS", "http://127.0.0.1:5174,http://localhost:5174"
    ).split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    return response


def serialize(user: User) -> UserRead:
    result = UserRead.model_validate(user, from_attributes=True)
    result.tags = [TagRead.model_validate(tag, from_attributes=True) for tag in user.tags]
    return result


def duplicate_error(exc: DuplicateUserField) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": f"{exc.field.upper()}_ALREADY_EXISTS", "field": exc.field},
    )


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail={"code": "DATABASE_UNAVAILABLE"}) from None
    return {"status": "ready"}


@app.get("/api/v1/users", response_model=list[UserRead], tags=["users"])
def list_users(
    search: Annotated[str | None, Query(max_length=120, pattern=r"^[^\x00]*$")] = None,
    include_inactive: bool = False,
    tag_id: UUID | None = None,
) -> list[UserRead]:
    with session_factory()() as session:
        users = UserRepository(session).list(
            search, include_inactive, str(tag_id) if tag_id else None
        )
        return [serialize(user) for user in users]


@app.get("/api/v1/tags", response_model=list[TagRead], tags=["tags"])
def list_tags() -> list[TagRead]:
    with session_factory()() as session:
        tags = UserRepository(session).list_tags()
        return [TagRead.model_validate(tag, from_attributes=True) for tag in tags]


@app.post("/api/v1/tags", response_model=TagRead, status_code=201, tags=["tags"])
def create_tag(payload: TagInput) -> TagRead:
    with session_factory()() as session:
        try:
            tag = UserRepository(session).create_tag(payload.name)
        except DuplicateTag:
            raise HTTPException(status_code=409, detail={"code": "TAG_ALREADY_EXISTS"}) from None
        return TagRead.model_validate(tag, from_attributes=True)


@app.post(
    "/api/v1/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=["users"]
)
def create_user(payload: UserInput) -> UserRead:
    with session_factory()() as session:
        try:
            user = UserRepository(session).create(
                username=payload.username,
                name=payload.name,
                email=str(payload.email),
                phone=payload.phone,
                tag_ids=[str(tag_id) for tag_id in payload.tag_ids],
            )
        except InvalidTags:
            raise HTTPException(status_code=422, detail={"code": "INVALID_TAGS"}) from None
        except DuplicateUserField as exc:
            raise duplicate_error(exc) from None
        return serialize(user)


@app.patch("/api/v1/users/{user_id}", response_model=UserRead, tags=["users"])
def update_user(user_id: UUID, payload: UserUpdate) -> UserRead:
    changes = payload.model_dump(exclude_unset=True)
    # Null is an explicit clear operation only for the optional phone field.
    # Null for required columns means "leave unchanged"; omission also leaves
    # every field unchanged.
    tag_ids = changes.pop("tag_ids", None)
    changes = {key: value for key, value in changes.items() if value is not None or key == "phone"}
    if not changes and tag_ids is None:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_UPDATE"})
    with session_factory()() as session:
        repository = UserRepository(session)
        user = repository.get(str(user_id))
        if user is None:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})
        if "email" in changes:
            changes["email"] = str(changes["email"])
        try:
            repository.update(
                user,
                changes,
                tag_ids=[str(tag_id) for tag_id in tag_ids] if tag_ids is not None else None,
            )
            return serialize(user)
        except DuplicateUserField as exc:
            raise duplicate_error(exc) from None
        except InvalidTags:
            raise HTTPException(status_code=422, detail={"code": "INVALID_TAGS"}) from None


@app.delete("/api/v1/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["users"])
def deactivate_user(user_id: UUID) -> Response:
    with session_factory()() as session:
        repository = UserRepository(session)
        user = repository.get(str(user_id))
        if user is None:
            raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})
        repository.deactivate(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
