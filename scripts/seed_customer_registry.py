#!/usr/bin/env python3
"""Idempotently add the synthetic Customer Registry demo users."""

from __future__ import annotations

import json
from pathlib import Path

from customer_registry.database import initialize_sqlite, session_factory
from customer_registry.models import User
from customer_registry.repositories.users import UserRepository
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/customer-registry/users.json"


def main() -> int:
    initialize_sqlite()
    users = json.loads(FIXTURE.read_text(encoding="utf-8"))
    inserted = 0
    with session_factory()() as session:
        repository = UserRepository(session)
        for row in users:
            exists = session.scalar(
                select(User.id).where(
                    (User.normalized_username == row["username"].casefold())
                    | (User.normalized_email == row["email"].casefold())
                )
            )
            if exists:
                continue
            repository.create(**row)
            inserted += 1
    print(
        json.dumps(
            {
                "schema": 1,
                "check": "seed-customer-registry",
                "status": "pass",
                "ok": 1,
                "metrics": {"fixture_users": len(users), "inserted": inserted},
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
