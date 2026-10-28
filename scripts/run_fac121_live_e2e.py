#!/usr/bin/env python3
"""Run one explicitly authorized Telegram outbox journey on disposable PostgreSQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages/task-engine/src"))
from task_engine.models import Demand, EventInbox, EventOutbox  # noqa: E402
from task_engine.transitions import apply_transition  # noqa: E402

from scripts.validate_env import read_env  # noqa: E402


def _read_quality_password() -> str:
    path = ROOT / ".runtime/quality/private/credentials.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    password = value.get("QUALITY_DB_PASSWORD")
    if not isinstance(password, str) or not re.fullmatch(r"[0-9a-f]{48}", password):
        raise ValueError("QUALITY_DATABASE_CREDENTIAL_INVALID")
    return password


def run(*, send_live: bool) -> dict:
    if not send_live:
        raise ValueError("EXPLICIT_LIVE_SEND_FLAG_REQUIRED")
    cfg = read_env(ROOT / ".env")
    token = cfg.get("TELEGRAM_BOT_TOKEN", "")
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
        raise ValueError("TELEGRAM_BOT_TOKEN_INVALID")
    chats = {
        int(item.strip())
        for item in cfg.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",")
        if item.strip()
    }
    if len(chats) != 1:
        raise ValueError("ONE_ALLOWLISTED_CHAT_REQUIRED_FOR_TEST")
    chat_id = next(iter(chats))
    pilot_path = ROOT / ".runtime/artifacts/telegram-pilot-2026-10-26.json"
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    reply_to = pilot.get("message_id")
    destination_hash = hashlib.sha256(str(chat_id).encode()).hexdigest()
    if (
        pilot.get("status") != "sent"
        or type(reply_to) is not int
        or reply_to < 1
        or pilot.get("destination_sha256") != destination_hash
    ):
        raise ValueError("ALLOWLISTED_SYNTHETIC_REPLY_ROOT_REQUIRED")

    password = _read_quality_password()
    db_name = f"fac121_{uuid.uuid4().hex[:20]}"
    admin_url = f"postgresql://quality:{quote(password, safe='')}@127.0.0.1:18832/factory"
    database_url = (
        f"postgresql+psycopg://quality:{quote(password, safe='')}@127.0.0.1:18832/{db_name}"
    )
    worker_env = ROOT / ".runtime/artifacts/fac-121/live-worker.env"
    worker_env.parent.mkdir(parents=True, exist_ok=True)
    demand_id = str(uuid.uuid4())
    transition_id: str | None = None
    created = False
    attempted_send = False
    outcome: dict = {"schema": 1, "activity": "FAC-121", "status": "error"}
    engine = None
    try:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        created = True
        env = {**os.environ, "DATABASE_URL": database_url, "FACTORY_ENV": "quality"}
        migration = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "apps/factory-api/alembic.ini",
                "upgrade",
                "head",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if migration.returncode:
            raise RuntimeError("DISPOSABLE_FACTORY_MIGRATION_FAILED")

        engine = create_engine(database_url, pool_pre_ping=True)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        with sessions.begin() as session:
            demand = Demand(
                id=demand_id,
                source="telegram",
                external_id=f"{chat_id}:{reply_to}",
                title="FAC-121 synthetic notification delivery check",
                demand_type="feature",
                status="new",
            )
            session.add(demand)
            session.flush()
            apply_transition(
                session,
                demand,
                entity_type="demand",
                new_state="triage",
                expected_version=1,
                actor="codex-delegated-test",
                reason="Synthetic live notification validation authorized by the operator.",
                idempotency_key=f"{demand_id}:triage",
            )
            transition = apply_transition(
                session,
                demand,
                entity_type="demand",
                new_state="blocked",
                expected_version=2,
                actor="codex-delegated-test",
                reason="Synthetic live notification validation authorized by the operator.",
                idempotency_key=f"{demand_id}:blocked",
            )
            transition_id = transition.id

        worker_env.write_text(
            "".join(
                (
                    f"DATABASE_URL={database_url}\n",
                    "TELEGRAM_SEND_ENABLED=true\n",
                    f"TELEGRAM_BOT_TOKEN={token}\n",
                    f"TELEGRAM_ALLOWED_CHAT_IDS={chat_id}\n",
                )
            ),
            encoding="utf-8",
        )
        worker_env.chmod(0o600)
        command = [
            sys.executable,
            "scripts/telegram_outbox_worker.py",
            "--env",
            str(worker_env),
            "--once",
            "--limit",
            "10",
        ]

        def dispatch() -> tuple[subprocess.CompletedProcess[str], dict]:
            result = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False
            )
            try:
                body = json.loads(result.stdout.strip().splitlines()[-1])
            except (IndexError, json.JSONDecodeError):
                body = {}
            return result, body

        attempted_send = True
        first, first_body = dispatch()
        if first.returncode or first_body != {"sent": 1, "failed": 0}:
            raise RuntimeError("TELEGRAM_LIVE_DISPATCH_FAILED")
        replay, replay_body = dispatch()
        if replay.returncode or replay_body != {"sent": 0, "failed": 0}:
            raise RuntimeError("TELEGRAM_LIVE_REPLAY_NOT_IDEMPOTENT")

        event_id = f"telegram-transition:{transition_id}"
        with sessions() as session:
            outbox = session.scalar(select(EventOutbox).where(EventOutbox.event_id == event_id))
            receipt = session.get(EventInbox, f"telegram-delivered:{event_id}")
            if (
                outbox is None
                or receipt is None
                or outbox.published_at is None
                or outbox.attempts != 1
            ):
                raise RuntimeError("TELEGRAM_DELIVERY_RECEIPT_MISSING")
            result = receipt.result
            if (
                result.get("reply_to_message_id") != reply_to
                or result.get("destination_sha256") != destination_hash
                or type(result.get("message_id")) is not int
                or result["message_id"] < 1
                or result.get("redaction_applied") is not True
            ):
                raise RuntimeError("TELEGRAM_DELIVERY_RECEIPT_MISMATCH")
            text = f"DEMAND-{demand_id}: status atualizado para blocked."
            outcome = {
                "schema": 1,
                "activity": "FAC-121",
                "status": "live_pass",
                "execution_kind": (
                    "live Telegram delivery from a persisted PostgreSQL demand transition"
                ),
                "database": {"name": db_name, "disposable": True, "migrations": "head"},
                "demand_id": demand_id,
                "transition_id": transition_id,
                "outbox_event_id": outbox.event_id,
                "outbox_id": outbox.id,
                "published_at": outbox.published_at.isoformat(),
                "attempts": outbox.attempts,
                "reply_to_message_id": reply_to,
                "reply_root": "previous synthetic bot marker (not an inbound intake message)",
                "telegram_message_id": result["message_id"],
                "destination_sha256": destination_hash,
                "notification_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "redaction_applied": result["redaction_applied"],
                "dispatch": first_body,
                "replay": replay_body,
                "sent_at": datetime.now(UTC).isoformat(),
            }
    except Exception as exc:
        outcome.update(
            status="delivery_unknown" if attempted_send else "error",
            error=str(exc) if str(exc).isupper() else type(exc).__name__,
            database={
                "name": db_name,
                "disposable": True,
                "preserved_for_reconciliation": created and attempted_send,
            },
        )
        # Keep the disposable DB when a provider call may have succeeded but
        # its receipt could not be verified; this allows safe reconciliation.
        if engine is not None:
            engine.dispose()
        if created and not attempted_send:
            with psycopg.connect(admin_url, autocommit=True) as conn:
                conn.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                    (db_name,),
                )
                conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))
        artifact = ROOT / ".runtime/artifacts/fac-121/live-transition-delivery.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        artifact.chmod(0o600)
        return outcome
    finally:
        worker_env.unlink(missing_ok=True)

    if engine is not None:
        engine.dispose()
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
            (db_name,),
        )
        conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name)))
    outcome["database"]["dropped_after_capture"] = True
    artifact = ROOT / ".runtime/artifacts/fac-121/live-transition-delivery.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    artifact.chmod(0o600)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--send-live",
        action="store_true",
        help="send one redacted message to the configured allowlist",
    )
    args = parser.parse_args()
    try:
        result = run(send_live=args.send_live)
    except Exception as exc:
        result = {
            "schema": 1,
            "activity": "FAC-121",
            "status": "error",
            "error": str(exc) if str(exc).isupper() else type(exc).__name__,
        }
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0 if result.get("status") == "live_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
