#!/usr/bin/env python3
"""Dispatch redacted Telegram outbox events when sending is explicitly enabled."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "workers/src"))
sys.path.insert(0, str(ROOT / "packages/integrations/src"))
sys.path.insert(0, str(ROOT / "packages/task-engine/src"))
sys.path.insert(0, str(ROOT / "packages/shared-contracts/src"))

from factory_workers.telegram_outbox import dispatch_pending_telegram  # noqa: E402
from integrations.telegram import TelegramError, TelegramNotifier  # noqa: E402

from scripts.telegram_intake_worker import parse_ids  # noqa: E402
from scripts.validate_env import read_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--once", action="store_true", help="dispatch one batch")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--authorized-demand-id",
        help="Explicit per-demand send authorization; never drains other threads",
    )
    parser.add_argument(
        "--authorized-event-id",
        help="Restrict delivery to one previously verified pending outbox event",
    )
    args = parser.parse_args()
    try:
        cfg = read_env(args.env)
        if not args.authorized_demand_id and cfg.get("TELEGRAM_SEND_ENABLED", "").lower() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            raise ValueError("TELEGRAM_SEND_DISABLED")
        chats = parse_ids(cfg.get("TELEGRAM_ALLOWED_CHAT_IDS", ""), "CHAT_IDS")
        token = cfg.get("TELEGRAM_BOT_TOKEN", "")
        database_url = cfg.get("DATABASE_URL", "")
        if not database_url:
            raise ValueError("DATABASE_URL_REQUIRED")
        if args.interval < 0.1:
            raise ValueError("POLL_INTERVAL_TOO_SMALL")
        if type(args.limit) is not int or not 1 <= args.limit <= 500:
            raise ValueError("TELEGRAM_OUTBOX_LIMIT_INVALID")

        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(database_url, pool_pre_ping=True)
        sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        roots = None
        event_ids = None
        if args.authorized_event_id and not args.authorized_demand_id:
            raise ValueError("TELEGRAM_EVENT_REQUIRES_DEMAND_AUTHORIZATION")
        if args.authorized_demand_id:
            from task_engine.models import Demand

            with sessions() as session:
                demand = session.get(Demand, args.authorized_demand_id)
                if demand is None or demand.source != "telegram":
                    raise ValueError("TELEGRAM_AUTHORIZED_DEMAND_REQUIRED")
                chat, message = demand.external_id.split(":", 1)
                roots = {(int(chat), int(message))}
                if args.authorized_event_id:
                    from task_engine.models import EventOutbox

                    event = session.scalar(
                        select(EventOutbox).where(
                            EventOutbox.event_id == args.authorized_event_id,
                            EventOutbox.event_type == "telegram.message.send",
                            EventOutbox.published_at.is_(None),
                        )
                    )
                    payload = event.payload if event is not None else {}
                    if (
                        not isinstance(payload, dict)
                        or payload.get("chat_id") != int(chat)
                        or payload.get("reply_to_message_id") != int(message)
                    ):
                        raise ValueError("TELEGRAM_EVENT_OUTSIDE_AUTHORIZED_DEMAND")
                    event_ids = {args.authorized_event_id}
        notifier = TelegramNotifier(token=token, allowed_chats=chats, enabled=True)
        while True:
            result = dispatch_pending_telegram(
                sessions,
                notifier,
                limit=args.limit,
                allowed_roots=roots,
                allowed_event_ids=event_ids,
            )
            print(json.dumps(result, separators=(",", ":")), flush=True)
            if args.once:
                break
            delay = max(args.interval, 30.0 if result["failed"] else 0.0)
            time.sleep(delay)
        engine.dispose()
        return 0
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, TelegramError, RuntimeError) as exc:
        code = str(exc) if re.fullmatch(r"[A-Z0-9_]+", str(exc)) else "TELEGRAM_WORKER_FAILED"
        print(json.dumps({"status": "error", "error": code}, separators=(",", ":")))
        return 1
    except Exception:
        print(json.dumps({"status": "error", "error": "TELEGRAM_WORKER_FAILED"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
