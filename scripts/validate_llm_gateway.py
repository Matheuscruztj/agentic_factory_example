#!/usr/bin/env python3
"""Validate the optional local LiteLLM gateway without exposing credentials."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_env import read_env  # noqa: E402


class GatewayError(ValueError):
    def __init__(self, category: str, code: str):
        super().__init__(code)
        self.category = category
        self.code = code


def _base_url(value: str, key: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise GatewayError("CONFIG", f"{key}_INVALID")
    return value.rstrip("/")


def _load_config(env_path: Path, config_path: Path) -> tuple[dict[str, str], dict]:
    try:
        env = read_env(env_path)
    except (OSError, ValueError) as exc:
        raise GatewayError("CONFIG", "ENV_INVALID") from exc
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GatewayError("CONFIG", "LITELLM_CONFIG_INVALID") from exc
    if not isinstance(config, dict) or not isinstance(config.get("model_list"), list):
        raise GatewayError("CONFIG", "MODEL_LIST_INVALID")
    names = [item.get("model_name") for item in config["model_list"] if isinstance(item, dict)]
    if not names or any(not isinstance(name, str) or not name for name in names):
        raise GatewayError("CONFIG", "MODEL_ALIAS_INVALID")
    if len(names) != len(set(names)):
        raise GatewayError("CONFIG", "MODEL_ALIAS_DUPLICATE")
    for item in config["model_list"]:
        params = item.get("litellm_params", {})
        model = params.get("model", "")
        if not isinstance(model, str) or not model.startswith(("ollama/", "ollama_chat/")):
            raise GatewayError("CONFIG", "NON_LOCAL_PROVIDER_FORBIDDEN")
        _base_url(params.get("api_base", ""), "OLLAMA_API_BASE")
    image_file = ROOT / "infra/compose/litellm.yml"
    try:
        compose = yaml.safe_load(image_file.read_text(encoding="utf-8"))
        image = compose["services"]["litellm"]["image"]
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise GatewayError("CONFIG", "LITELLM_IMAGE_INVALID") from exc
    if not re.fullmatch(r"ghcr\.io/berriai/litellm:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", image):
        raise GatewayError("CONFIG", "LITELLM_IMAGE_NOT_PINNED")
    enabled = env.get("LITELLM_ENABLED", "false").strip().lower()
    if enabled not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise GatewayError("CONFIG", "LITELLM_ENABLED_INVALID")
    if enabled in {"true", "1", "yes", "on"}:
        _validate_secret(env)
        _base_url(env.get("LITELLM_BASE_URL", "http://127.0.0.1:4000"), "LITELLM_BASE_URL")
    return env, config


def _validate_secret(env: dict[str, str]) -> str:
    key = env.get("LITELLM_MASTER_KEY", "")
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{24,}", key):
        raise GatewayError("CONFIG", "LITELLM_MASTER_KEY_INVALID")
    return key


def _dry_run(env: dict[str, str]) -> None:
    child_env = {**os.environ, **env}
    # Compose resolves required variables even when an optional profile is only
    # being checked. Use a non-persistent sentinel only for this config parse.
    if not child_env.get("LITELLM_MASTER_KEY"):
        child_env["LITELLM_MASTER_KEY"] = "sk-dry-run-only-sentinel-0000000000000000"
    commands = [
        [
            "docker",
            "compose",
            "-f",
            "infra/compose/ai-services.yml",
            "-f",
            "infra/compose/litellm.yml",
            "config",
            "--quiet",
        ],
        [
            "docker",
            "compose",
            "--profile",
            "litellm",
            "-f",
            "infra/compose/ai-services.yml",
            "-f",
            "infra/compose/litellm.yml",
            "config",
            "--quiet",
        ],
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=child_env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise GatewayError("NETWORK", "COMPOSE_UNAVAILABLE") from None
        if result.returncode:
            raise GatewayError("CONFIG", "COMPOSE_CONFIG_INVALID")


def _get_json(url: str, *, headers: dict[str, str] | None = None) -> dict:
    try:
        response = httpx.get(url, headers=headers, timeout=5, trust_env=False)
    except httpx.HTTPError:
        raise GatewayError("NETWORK", "NETWORK") from None
    if response.status_code in {401, 403}:
        raise GatewayError("AUTH", "HTTP_401")
    if response.status_code == 404:
        raise GatewayError("CONFIG", "ENDPOINT_MISSING")
    if response.status_code >= 500:
        raise GatewayError("NETWORK", f"HTTP_{response.status_code}")
    if response.status_code >= 400:
        raise GatewayError("CONFIG", f"HTTP_{response.status_code}")
    try:
        value = response.json()
    except ValueError:
        raise GatewayError("CONFIG", "RESPONSE_INVALID") from None
    if not isinstance(value, dict):
        raise GatewayError("CONFIG", "RESPONSE_INVALID")
    return value


def _live(env: dict[str, str], config: dict) -> None:
    if env.get("LITELLM_ENABLED", "false").strip().lower() not in {"true", "1", "yes", "on"}:
        raise GatewayError("CONFIG", "GATEWAY_DISABLED")
    key = _validate_secret(env)
    gateway = _base_url(env.get("LITELLM_BASE_URL", "http://127.0.0.1:4000"), "LITELLM_BASE_URL")
    ollama = _base_url(env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), "OLLAMA_BASE_URL")
    _get_json(f"{gateway}/health/liveness")
    models = _get_json(f"{gateway}/v1/models", headers={"Authorization": f"Bearer {key}"})
    available = {
        item.get("id") for item in models.get("data", []) if isinstance(item, dict)
    }
    expected = {item["model_name"] for item in config["model_list"]}
    if not expected <= available:
        raise GatewayError("CONFIG", "MODEL_MISSING")
    tags = _get_json(f"{ollama}/api/tags")
    ollama_names = {
        item.get("name") for item in tags.get("models", []) if isinstance(item, dict)
    }
    configured = {
        item["litellm_params"]["model"].removeprefix("ollama_chat/").removeprefix("ollama/")
        for item in config["model_list"]
    }
    missing = configured - ollama_names
    if missing:
        raise GatewayError("CONFIG", "MODEL_MISSING")


def run(mode: str, env_path: Path, config_path: Path) -> tuple[int, dict]:
    checks = []
    try:
        env, config = _load_config(env_path, config_path)
        checks.append({"name": "syntax", "status": "pass"})
        if mode == "dry-run":
            _dry_run(env)
            checks.append({"name": "compose_profiles", "status": "pass"})
        elif mode == "live":
            _live(env, config)
            checks.append({"name": "local_gateway_and_ollama", "status": "pass"})
        return 0, {"status": "pass", "mode": mode, "checks": checks}
    except GatewayError as exc:
        code = 1 if exc.category in {"CONFIG", "AUTH"} else 2
        return code, {
            "status": "fail" if code == 1 else "error",
            "mode": mode,
            "checks": checks,
            "error": {"category": exc.category, "code": exc.code},
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("syntactic", "dry-run", "live"), default="syntactic")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--config", type=Path, default=ROOT / "infra/litellm/config.example.yaml"
    )
    args = parser.parse_args()
    code, result = run(args.mode, args.env, args.config)
    print(json.dumps(result, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
