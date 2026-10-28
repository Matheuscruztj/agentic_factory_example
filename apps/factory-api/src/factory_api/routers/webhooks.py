"""Opt-in GitHub webhook intake with HMAC verification and no implicit execution."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from task_engine.models import AuditRecord, Demand, RequirementRevision

from factory_api.database import get_db

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
_MAX_BODY = 1_000_000


@router.post("/github")
async def github_webhook(
    request: Request,
    signature: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    event: str | None = Header(default=None, alias="X-GitHub-Event"),
    delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    db: Session = Depends(get_db),
) -> dict:
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=404, detail={"code": "WEBHOOK_DISABLED"})
    raw = await request.body()
    if len(raw) > _MAX_BODY:
        raise HTTPException(status_code=413, detail={"code": "WEBHOOK_BODY_TOO_LARGE"})
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail={"code": "WEBHOOK_SIGNATURE_INVALID"})
    if not delivery or not re.fullmatch(r"[0-9a-fA-F-]{16,64}", delivery):
        raise HTTPException(status_code=400, detail={"code": "WEBHOOK_DELIVERY_INVALID"})
    if event != "issues":
        return {"accepted": False, "reason": "EVENT_IGNORED", "delivery_id": delivery}
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail={"code": "WEBHOOK_JSON_INVALID"}) from None
    if not isinstance(payload, dict) or payload.get("action") not in {
        "opened", "reopened", "edited"
    }:
        return {"accepted": False, "reason": "ACTION_IGNORED", "delivery_id": delivery}
    issue = payload.get("issue")
    repository = payload.get("repository")
    if not isinstance(issue, dict) or not isinstance(repository, dict):
        raise HTTPException(status_code=422, detail={"code": "WEBHOOK_ISSUE_INVALID"})
    number, title = issue.get("number"), issue.get("title")
    repo_full_name = repository.get("full_name")
    if type(number) is not int or number < 1 or not isinstance(title, str) or not title.strip():
        raise HTTPException(status_code=422, detail={"code": "WEBHOOK_ISSUE_INVALID"})
    repository_pattern = r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    if not isinstance(repo_full_name, str) or not re.fullmatch(repository_pattern, repo_full_name):
        raise HTTPException(status_code=422, detail={"code": "WEBHOOK_REPOSITORY_INVALID"})
    allowed_repositories = {
        value.strip().casefold()
        for value in os.getenv("GITHUB_ALLOWED_REPOSITORIES", "").split(",")
        if value.strip()
    }
    if not allowed_repositories or repo_full_name.casefold() not in allowed_repositories:
        raise HTTPException(status_code=403, detail={"code": "WEBHOOK_REPOSITORY_FORBIDDEN"})
    source_id = f"{repo_full_name}#{number}"
    existing = db.scalar(
        select(Demand).where(Demand.source == "github", Demand.external_id == source_id)
    )
    if existing is not None:
        return {"accepted": True, "demand_id": existing.id, "duplicate": True}
    body = issue.get("body") if isinstance(issue.get("body"), str) else ""
    requirement = f"GitHub issue {source_id}\n\n{body[:20000]}"
    demand = Demand(
        source="github", external_id=source_id, title=title.strip()[:240],
        demand_type="bug", status="new", version=1, state_version=1,
        risk="normal", repository_id=repo_full_name,
    )
    db.add(demand)
    db.flush()
    db.add(RequirementRevision(
        demand_id=demand.id, version=1, content=requirement,
        acceptance=["Issue reviewed by operator before task execution"], decision="proposed",
    ))
    db.add(AuditRecord(
        subject_type="demand", subject_id=demand.id, action="webhook.github.issue_received",
        actor="github-webhook", details={"delivery_id": delivery, "issue": source_id},
        evidence_hashes=[hashlib.sha256(raw).hexdigest()],
    ))
    db.commit()
    return {
        "accepted": True,
        "demand_id": demand.id,
        "duplicate": False,
        "execution_started": False,
    }
