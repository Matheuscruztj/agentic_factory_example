#!/usr/bin/env python3
"""Continuously poll one fixed GitHub repository into the local demand intake."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "workers/src"),
    str(ROOT / "packages/integrations/src"),
    str(ROOT / "packages/task-engine/src"),
    str(ROOT / "packages/shared-contracts/src"),
]

from factory_workers.github_cursor import JsonCursorStore  # noqa: E402
from factory_workers.github_poll import poll_github_into_database  # noqa: E402
from integrations.github import GitHubClient  # noqa: E402

from scripts.validate_env import read_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=60)
    args = parser.parse_args()
    engine = None
    try:
        cfg = read_env(args.env)
        if cfg.get("GITHUB_ENABLED", "false").casefold() not in {"1", "true", "yes", "on"}:
            raise ValueError("GITHUB_INTAKE_DISABLED")
        if cfg.get("GITHUB_AUTH_MODE", "pat").casefold() != "pat":
            raise ValueError("GITHUB_APP_TOKEN_PROVIDER_REQUIRED")
        owner, repo, token = (
            cfg.get(key, "").strip() for key in ("GITHUB_OWNER", "GITHUB_REPO", "GITHUB_TOKEN")
        )
        database_url = cfg.get("DATABASE_URL", "").strip()
        if not owner or not repo or not token or not database_url:
            raise ValueError("GITHUB_WORKER_CONFIGURATION_REQUIRED")
        if args.interval < 1:
            raise ValueError("POLL_INTERVAL_TOO_SMALL")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(database_url, pool_pre_ping=True)
        sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        client = GitHubClient(
            owner=owner,
            repo=repo,
            token=token,
            api_url=cfg.get("GITHUB_API_URL", "https://api.github.com"),
        )
        client.verify_repository_access()
        cursor = JsonCursorStore(ROOT / ".runtime/github-cursor.json")
        backoff = 1.0
        while True:
            try:
                result = poll_github_into_database(
                    client,
                    session_factory=sessions,
                    cursor_store=cursor,
                    now=datetime.now(UTC),
                    overlap=timedelta(seconds=int(cfg.get("GITHUB_POLL_OVERLAP_SECONDS", "300"))),
                )
                print(json.dumps(result, separators=(",", ":")), flush=True)
                backoff = 1.0
                if args.once:
                    return 0
                time.sleep(args.interval)
            except KeyboardInterrupt:
                return 0
            except Exception as exc:
                code = str(exc) if re.fullmatch(r"[A-Z0-9_:-]+", str(exc)) else "GITHUB_POLL_FAILED"
                print(
                    json.dumps({"status": "error", "error": code}, separators=(",", ":")),
                    flush=True,
                )
                if args.once:
                    return 1
                time.sleep(min(backoff, 300))
                backoff = min(backoff * 2, 300)
    except (OSError, ValueError, RuntimeError) as exc:
        code = str(exc) if re.fullmatch(r"[A-Z0-9_:-]+", str(exc)) else "GITHUB_WORKER_FAILED"
        print(json.dumps({"status": "error", "error": code}, separators=(",", ":")))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
