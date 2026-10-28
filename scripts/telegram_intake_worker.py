#!/usr/bin/env python3
"""Run one or more controlled Telegram intake polls using the local .env."""

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

from factory_workers.telegram_commands import telegram_command_handler  # noqa: E402
from factory_workers.telegram_offset import TelegramOffsetStore  # noqa: E402
from factory_workers.telegram_poll import poll_telegram_into_database  # noqa: E402
from integrations.telegram import TelegramError, TelegramPoller  # noqa: E402

from scripts.validate_env import read_env  # noqa: E402


def parse_ids(value: str, key: str) -> set[int]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts or any(not re.fullmatch(r"-?\d+", part) for part in parts):
        raise ValueError(f"{key}_INVALID")
    return {int(part) for part in parts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--once", action="store_true", help="process one getUpdates cycle")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    try:
        cfg = read_env(args.env)
        if cfg.get("TELEGRAM_ENABLED", "").lower() not in {"1", "true", "yes", "on"}:
            raise ValueError("TELEGRAM_INTAKE_DISABLED")
        chats = parse_ids(cfg.get("TELEGRAM_ALLOWED_CHAT_IDS", ""), "CHAT_IDS")
        users = parse_ids(cfg.get("TELEGRAM_ALLOWED_USER_IDS", ""), "USER_IDS")
        token = cfg.get("TELEGRAM_BOT_TOKEN", "")
        database_url = cfg.get("DATABASE_URL", "")
        if not database_url:
            raise ValueError("DATABASE_URL_REQUIRED")
        if args.interval < 0.1:
            raise ValueError("POLL_INTERVAL_TOO_SMALL")

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(database_url, pool_pre_ping=True)
        session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        poller = TelegramPoller(
            token=token, allowed_chats=chats, allowed_users=users, enabled=True
        )
        command_handler = telegram_command_handler(
            users, ui_url=cfg.get("TELEGRAM_FACTORY_UI_URL") or None
        )
        offsets = TelegramOffsetStore(ROOT / ".runtime/telegram-offset.json")
        while True:
            result = poll_telegram_into_database(
                poller,
                session_factory=session_factory,
                offset_store=offsets,
                command_handler=command_handler,
            )
            print(json.dumps(result, separators=(",", ":")), flush=True)
            if args.once:
                break
            time.sleep(args.interval)
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
