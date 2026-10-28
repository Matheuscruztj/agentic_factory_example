"""Start only the disposable quality API, after migrating its own database."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("application", choices=("factory", "registry"))
    args = parser.parse_args()
    if os.getenv("FACTORY_ENV") != "quality":
        raise RuntimeError("DISPOSABLE_QUALITY_ENVIRONMENT_REQUIRED")
    key = "DATABASE_URL" if args.application == "factory" else "REGISTRY_DATABASE_URL"
    url = urlsplit(os.environ.get(key, ""))
    if url.hostname != "quality-postgres" or url.username != "quality":
        raise RuntimeError("DISPOSABLE_QUALITY_DATABASE_REQUIRED")
    config = (
        "apps/factory-api/alembic.ini"
        if args.application == "factory"
        else "apps/customer-registry/api/alembic.ini"
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", config, "upgrade", "head"],
        cwd=ROOT,
        check=False,
        timeout=120,
    )
    if result.returncode:
        return result.returncode
    module = (
        "factory_api.main:app" if args.application == "factory" else "customer_registry.main:app"
    )
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            module,
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--no-access-log",
        ],
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
