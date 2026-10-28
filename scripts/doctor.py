#!/usr/bin/env python3
"""Report configured, reachable and functional local services for a selected profile."""

from __future__ import annotations

import argparse
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class Probe:
    configured: bool
    reachable: bool
    functional: bool
    required: bool


def request(url: str, *, headers: dict[str, str] | None = None) -> tuple[bool, Any]:
    try:
        with httpx.stream(
            "GET",
            url,
            headers=headers or {},
            timeout=2,
            follow_redirects=False,
            trust_env=False,
        ) as response:
            if response.is_error:
                return True, {"http_status": response.status_code}
            raw = bytearray()
            for chunk in response.iter_bytes():
                if len(raw) + len(chunk) > 1_000_000:
                    return True, None
                raw.extend(chunk)
            if len(raw) > 1_000_000:
                return True, None
            try:
                return True, json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                return True, None
    except httpx.HTTPError:
        return False, None


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key and key.replace("_", "").isalnum():
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


def http_probe(url: str, *, required: bool) -> Probe:
    configured = bool(url)
    if not configured:
        return Probe(False, False, False, required)
    reachable, payload = request(url)
    functional = reachable and isinstance(payload, dict) and payload.get("status") in {
        "ok", "ready"
    }
    return Probe(configured, reachable, functional, required)


def ollama_probe(url: str, *, required: bool) -> Probe:
    if not url:
        return Probe(False, False, False, required)
    reachable, payload = request(url.rstrip("/") + "/api/tags")
    names = (
        {
            item.get("name")
            for item in payload.get("models", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        if isinstance(payload, dict)
        else set()
    )
    configured_models = {
        os.getenv("OLLAMA_MODEL_CHAT", "").strip(),
        os.getenv("OLLAMA_MODEL_CODING", "").strip(),
    } - {""}
    functional = reachable and bool(names) and (not required or configured_models.issubset(names))
    return Probe(True, reachable, functional, required)


def openbot_probe(url: str, *, enabled: bool, api_key: str, required: bool) -> Probe:
    if not enabled:
        return Probe(False, False, False, False)
    if not url or not api_key:
        return Probe(False, False, False, required)
    health, payload = request(
        url.rstrip("/") + os.getenv("OPENBOT_HEALTH_PATH", "/api/v1/health")
    )
    authenticated, auth_payload = request(
        url.rstrip("/") + os.getenv("OPENBOT_AUTH_PROBE_PATH", "/api/v1/providers"),
        headers={"X-API-Key": api_key},
    )
    functional = (
        health
        and isinstance(payload, dict)
        and payload.get("status") in {"ok", "ready"}
        and authenticated
        and not (isinstance(auth_payload, dict) and "http_status" in auth_payload)
    )
    return Probe(True, health and authenticated, functional, required)


def port_probe(host: str, port: int, *, configured: bool, required: bool) -> Probe:
    if not configured:
        return Probe(False, False, False, required)
    try:
        with socket.create_connection((host, port), timeout=1):
            return Probe(True, True, True, required)
    except OSError:
        return Probe(True, False, False, required)


def database_probe(url: str, *, required: bool) -> Probe:
    if not url:
        return Probe(False, False, False, required)
    try:
        import psycopg

        dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)
        with psycopg.connect(dsn, connect_timeout=2) as connection:
            connection.execute("SELECT 1").fetchone()
        return Probe(True, True, True, required)
    except ImportError:
        reachable = port_probe("127.0.0.1", 5432, configured=True, required=required).reachable
        return Probe(True, reachable, False, required)
    except Exception:
        return Probe(True, False, False, required)


def redis_probe(url: str, *, required: bool) -> Probe:
    if not url:
        return Probe(False, False, False, required)
    parsed = urlsplit(url)
    if not parsed.hostname or not parsed.port:
        return Probe(True, False, False, required)
    try:
        with socket.create_connection((parsed.hostname, parsed.port), timeout=1) as sock:
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = sock.recv(64)
        return Probe(True, True, response.startswith(b"+PONG"), required)
    except OSError:
        return Probe(True, False, False, required)


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("registry", "factory", "agent"), default="registry")
    args = parser.parse_args()
    registry_url = os.getenv("REGISTRY_API_URL", "http://127.0.0.1:8010")
    factory_url = os.getenv("FACTORY_API_URL", "http://127.0.0.1:8001")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    openbot_url = os.getenv("OPENBOT_BASE_URL", "http://127.0.0.1:8002")
    openbot_enabled = os.getenv("OPENBOT_ENABLED", "false").lower() in {"true", "1", "yes"}
    openbot_key = os.getenv("OPENBOT_API_KEY", "")
    redis_enabled = os.getenv("REDIS_ENABLED", "false").lower() in {"true", "1", "yes"}
    profiles: dict[str, dict[str, bool]] = {
        "registry": {"registry_api": True},
        "factory": {"factory_api": True, "factory_db": True, "redis": redis_enabled},
        "agent": {
            "factory_api": True,
            "factory_db": True,
            "redis": redis_enabled,
            "ollama": True,
            "openbot": False,
        },
    }
    required = profiles[args.profile]
    checks = {
        "registry_api": http_probe(
            registry_url + "/health/ready", required=required.get("registry_api", False)
        ),
        "factory_api": http_probe(
            factory_url + "/health/ready", required=required.get("factory_api", False)
        ),
        "registry_db": database_probe(
            os.getenv("REGISTRY_DATABASE_URL", ""), required=required.get("registry_db", False)
        ),
        "factory_db": database_probe(
            os.getenv("DATABASE_URL", ""), required=required.get("factory_db", False)
        ),
        "redis": redis_probe(
            os.getenv("REDIS_URL", "") if redis_enabled else "",
            required=required.get("redis", False),
        ),
        "ollama": ollama_probe(ollama_url, required=required.get("ollama", False)),
        "openbot": openbot_probe(
            openbot_url,
            enabled=openbot_enabled,
            api_key=openbot_key,
            required=required.get("openbot", False),
        ),
    }
    output = {
        "schema": 2,
        "check": "doctor",
        "profile": args.profile,
        "status": "pass"
        if all(not item.required or item.functional for item in checks.values())
        else "error",
        "services": {
            name: {
                "configured": item.configured,
                "reachable": item.reachable,
                "functional": item.functional,
                "required": item.required,
            }
            for name, item in checks.items()
        },
    }
    print(json.dumps(output, separators=(",", ":")))
    return 0 if output["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
