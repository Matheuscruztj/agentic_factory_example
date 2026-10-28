"""Operator-approved, content-addressed prompt promotion and rollback."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from task_engine.models import AuditRecord, PromptRelease

from factory_api.config import Settings
from factory_api.database import get_db
from factory_api.operator import require_operator

router = APIRouter(
    prefix="/api/v1/prompts/releases",
    tags=["prompt-releases"],
    dependencies=[Depends(require_operator)],
)
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
_HASH = re.compile(r"^[a-f0-9]{64}$")
_PROMPT_DIR = Path(__file__).resolve().parents[5] / "agents" / "prompts"
_EXPERIMENT_REPORT = (
    Path(__file__).resolve().parents[5] / ".runtime" / "evals" / "prompt-experiment.json"
)


class ReleaseRequest(BaseModel):
    version: str = Field(min_length=1, max_length=120)
    prompt_hash: str
    experiment_sha256: str


def _read_prompt(version: str) -> str:
    if not _NAME.fullmatch(version):
        raise HTTPException(status_code=422, detail={"code": "PROMPT_VERSION_INVALID"})
    path = _PROMPT_DIR / f"{version}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=404, detail={"code": "PROMPT_VERSION_NOT_FOUND"}) from exc


def _release(
    payload: ReleaseRequest,
    operator: dict,
    db: Session,
    *,
    action: str,
) -> dict:
    if not Settings.from_env().auth_enabled:
        raise HTTPException(status_code=403, detail={"code": "AUTH_REQUIRED_FOR_PROMPT_RELEASE"})
    if not _HASH.fullmatch(payload.prompt_hash) or not _HASH.fullmatch(payload.experiment_sha256):
        raise HTTPException(status_code=422, detail={"code": "PROMPT_RELEASE_HASH_INVALID"})
    prompt = _read_prompt(payload.version)
    if hashlib.sha256(prompt.encode("utf-8")).hexdigest() != payload.prompt_hash:
        raise HTTPException(status_code=409, detail={"code": "PROMPT_HASH_MISMATCH"})
    try:
        experiment_bytes = _EXPERIMENT_REPORT.read_bytes()
        experiment = json.loads(experiment_bytes)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=409, detail={"code": "PROMPT_REGRESSION_REPORT_MISSING"}
        ) from None
    if hashlib.sha256(experiment_bytes).hexdigest() != payload.experiment_sha256:
        raise HTTPException(status_code=409, detail={"code": "PROMPT_REGRESSION_HASH_MISMATCH"})
    if not isinstance(experiment, dict):
        raise HTTPException(status_code=409, detail={"code": "PROMPT_REGRESSION_REPORT_INVALID"})
    candidate = experiment.get("candidate", {})
    comparison = experiment.get("comparison", {})
    if (
        experiment.get("promotion_eligible") is not True
        or candidate.get("prompt_hash") != payload.prompt_hash
        or comparison.get("critical_regressions") != []
    ):
        raise HTTPException(status_code=409, detail={"code": "PROMPT_REGRESSION_NOT_PASSED"})

    current = db.scalar(
        select(PromptRelease).where(PromptRelease.active.is_(True)).order_by(PromptRelease.created_at.desc())
    )
    if action == "rollback":
        if current is None or current.version == payload.version:
            raise HTTPException(status_code=409, detail={"code": "ROLLBACK_TARGET_MUST_DIFFER"})
    elif current is not None and current.version == payload.version:
        raise HTTPException(status_code=409, detail={"code": "PROMPT_ALREADY_ACTIVE"})

    if current is not None:
        current.active = False
    row = PromptRelease(
        version=payload.version,
        prompt_hash=payload.prompt_hash,
        previous_version=current.version if current else None,
        previous_hash=current.prompt_hash if current else None,
        action=action,
        actor=str(operator.get("sub", "operator")),
        experiment_sha256=payload.experiment_sha256,
        active=True,
    )
    db.add(row)
    db.flush()
    db.add(
        AuditRecord(
            subject_type="prompt",
            subject_id=payload.version,
            action=f"prompt.{action}",
            actor=row.actor,
            details={
                "release_id": row.id,
                "prompt_hash": payload.prompt_hash,
                "previous_version": row.previous_version,
                "experiment_sha256": payload.experiment_sha256,
            },
            evidence_hashes=[payload.prompt_hash, payload.experiment_sha256],
        )
    )
    db.commit()
    return {
        "release_id": row.id,
        "version": row.version,
        "prompt_hash": row.prompt_hash,
        "previous_version": row.previous_version,
        "action": row.action,
        "active": row.active,
        "actor": row.actor,
    }


@router.get("")
def active_release(db: Session = Depends(get_db)) -> dict:
    row = db.scalar(
        select(PromptRelease).where(PromptRelease.active.is_(True)).order_by(PromptRelease.created_at.desc())
    )
    if row is None:
        return {"active": None, "history": []}
    history: Sequence[PromptRelease] = db.scalars(
        select(PromptRelease).order_by(PromptRelease.created_at.desc())
    ).all()
    return {
        "active": {"version": row.version, "prompt_hash": row.prompt_hash},
        "history": [
            {
                "version": item.version,
                "prompt_hash": item.prompt_hash,
                "action": item.action,
                "actor": item.actor,
                "created_at": item.created_at.isoformat(),
            }
            for item in history
        ],
    }


@router.post("/promote", status_code=201)
def promote(
    payload: ReleaseRequest,
    operator: dict = Depends(require_operator),
    db: Session = Depends(get_db),
) -> dict:
    return _release(payload, operator, db, action="promote")


@router.post("/rollback", status_code=201)
def rollback(
    payload: ReleaseRequest,
    operator: dict = Depends(require_operator),
    db: Session = Depends(get_db),
) -> dict:
    return _release(payload, operator, db, action="rollback")
