#!/usr/bin/env python3
"""Report local app and optional service availability without exposing configuration."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request


def probe_http(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def probe_port(host: str, port: int, timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    checks = {
        "factory_api": probe_http(
            os.getenv("FACTORY_API_URL", "http://127.0.0.1:8001") + "/health/live"
        ),
        "registry_api": probe_http(
            os.getenv("REGISTRY_API_URL", "http://127.0.0.1:8010") + "/health/live"
        ),
        "postgres": probe_port("127.0.0.1", int(os.getenv("POSTGRES_PORT", "5432"))),
        "redis": probe_port("127.0.0.1", 6379),
    }
    print(
        json.dumps(
            {
                "schema": 1,
                "check": "doctor",
                "status": "pass" if checks["registry_api"] else "error",
                "ok": int(checks["registry_api"]),
                "services": checks,
            },
            separators=(",", ":"),
        )
    )
    return 0 if checks["registry_api"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
