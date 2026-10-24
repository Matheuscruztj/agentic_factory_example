"""Audit records, immutable snapshots, and content-addressed local artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from sqlalchemy.orm import Session

from task_engine.models import (
    Artifact,
    AuditRecord,
    Demand,
    EntitySnapshot,
    RequirementRevision,
    Task,
)

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def record_audit(
    session: Session,
    *,
    subject_type: str,
    subject_id: str,
    action: str,
    actor: str,
    details: dict | None = None,
    evidence_hashes: list[str] | None = None,
) -> AuditRecord:
    if not actor.strip() or not action.strip():
        raise ValueError("AUDIT_METADATA_REQUIRED")
    record = AuditRecord(
        subject_type=subject_type,
        subject_id=subject_id,
        action=action,
        actor=actor.strip(),
        details=details or {},
        evidence_hashes=evidence_hashes or [],
    )
    session.add(record)
    session.flush()
    return record


def store_artifact(
    session: Session,
    root: str | Path,
    *,
    subject_type: str,
    subject_id: str,
    name: str,
    content: bytes,
    media_type: str = "application/octet-stream",
) -> Artifact:
    """Store bytes only below root/artifacts/<subject_type>/<subject_id>/ with no traversal."""
    if not _SAFE_SEGMENT.fullmatch(subject_type) or not _SAFE_SEGMENT.fullmatch(subject_id):
        raise ValueError("INVALID_ARTIFACT_SUBJECT")
    name_path = Path(name)
    if name_path.is_absolute() or len(name_path.parts) != 1 or not _SAFE_SEGMENT.fullmatch(name):
        raise ValueError("INVALID_ARTIFACT_PATH")
    root_path = Path(root).resolve()
    relative = Path("artifacts") / subject_type / subject_id / name
    target = (root_path / relative).resolve()
    if not target.is_relative_to(root_path):
        raise ValueError("ARTIFACT_PATH_NOT_ALLOWED")
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content).hexdigest()
    # Atomic replace prevents readers seeing a partial artifact.
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_bytes(content)
    os.replace(tmp, target)
    row = Artifact(
        subject_type=subject_type,
        subject_id=subject_id,
        relative_path=relative.as_posix(),
        sha256=digest,
        size_bytes=len(content),
        media_type=media_type,
    )
    session.add(row)
    session.flush()
    return row


def snapshot_entity(
    session: Session, entity: Demand | Task, *, entity_type: str, version: int | None = None
) -> EntitySnapshot:
    if entity_type not in {"demand", "task"} or not isinstance(
        entity, Demand if entity_type == "demand" else Task
    ):
        raise ValueError("SNAPSHOT_ENTITY_TYPE_MISMATCH")
    payload = {column.name: getattr(entity, column.name) for column in entity.__table__.columns}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    payload = json.loads(canonical)
    entity_version = (
        version
        if version is not None
        else entity.version
        if isinstance(entity, Demand)
        else entity.state_version
    )
    row = EntitySnapshot(
        entity_type=entity_type,
        entity_id=entity.id,
        version=entity_version,
        content=payload,
        sha256=digest,
    )
    session.add(row)
    session.flush()
    return row


def render_approved_requirement(revision: RequirementRevision) -> str:
    if revision.decision != "approved":
        raise ValueError("REQUIREMENT_NOT_APPROVED")
    acceptance = "\n".join(f"- {item}" for item in revision.acceptance)
    header = f"# Requisito aprovado (v{revision.version})"
    return f"{header}\n\n{revision.content}\n\n## Aceite\n{acceptance}\n"
