#!/usr/bin/env python3
"""Secure first-run .env creation for *local* development. Never prints secrets.

Only overwrites .env if it is byte-for-byte equal to the distributable template.
Exit 0 configured; 1 user/config refusal; 2 operational error. Stdout one JSON line.
Password hash format: scrypt:16384:8:1:<salt hex>:<digest hex>.
The application auth verifier must implement the same encoding.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path


def derive(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=32)
    return "scrypt:16384:8:1:" + salt.hex() + ":" + digest.hex()


def install(root: Path, ask=None) -> tuple[int, dict]:
    template = root / ".env.example"
    dest = root / ".env"
    if not template.is_file():
        return 2, {"check": "local-env-init", "ok": 0, "reason": "TEMPLATE_MISSING"}
    original = template.read_text(encoding="utf-8")
    if dest.is_file():
        current = dest.read_text(encoding="utf-8")
        if current != original:
            return 1, {
                "check": "local-env-init",
                "ok": 0,
                "reason": "ENV_ALREADY_CONFIGURED_NO_OVERWRITE",
            }
    if ask is None:
        ask = getpass.getpass
    try:
        password = ask("Choose local operator password (min 14 chars): ")
        confirm = ask("Confirm local operator password: ")
    except (EOFError, KeyboardInterrupt):
        return 2, {"check": "local-env-init", "ok": 0, "reason": "INTERACTIVE_PASSWORD_REQUIRED"}
    if password != confirm or len(password) < 14:
        return 1, {"check": "local-env-init", "ok": 0, "reason": "PASSWORD_MISMATCH_OR_TOO_SHORT"}
    app_key = secrets.token_urlsafe(48)
    db_password = secrets.token_urlsafe(32)
    data = original.replace("APP_SECRET_KEY=\n", f"APP_SECRET_KEY={app_key}\n", 1)
    data = data.replace(
        "OPERATOR_PASSWORD_HASH=\n", f"OPERATOR_PASSWORD_HASH={derive(password)}\n", 1
    )
    if "REPLACE_WITH_STRONG_LOCAL_PASSWORD" not in data:
        return 2, {"check": "local-env-init", "ok": 0, "reason": "DB_PLACEHOLDER_MISSING"}
    data = data.replace("REPLACE_WITH_STRONG_LOCAL_PASSWORD", db_password)
    # Use exclusive write on fresh creation; when a template .env exists, replace only exact template.
    temp = root / ".env.setup.tmp"
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
        os.replace(temp, dest)
        if os.name == "posix":
            os.chmod(dest, 0o600)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        return 2, {"check": "local-env-init", "ok": 0, "reason": "ENV_WRITE_FAILED"}
    return 0, {
        "check": "local-env-init",
        "ok": 1,
        "status": "pass",
        "metrics": {"fields_initialized": 3},
        "detail": "LOCAL_SECRETS_WRITTEN_NOT_PRINTED",
    }


if __name__ == "__main__":
    code, result = install(Path(__file__).resolve().parents[1])
    print(json.dumps(result, separators=(",", ":")))
    sys.exit(code)
