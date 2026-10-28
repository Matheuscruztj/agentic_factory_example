from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts" / "validate_llm_gateway.py"
spec = importlib.util.spec_from_file_location("validate_llm_gateway", MODULE)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


def test_syntactic_cli_emits_one_json_line_and_does_not_need_secrets(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("LITELLM_ENABLED=false\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(MODULE), "--mode", "syntactic", "--env", str(env_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 1
    assert json.loads(result.stdout)["status"] == "pass"


def test_enabled_gateway_rejects_missing_or_weak_key_without_echoing(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("LITELLM_ENABLED=true\nLITELLM_MASTER_KEY=short\n", encoding="utf-8")
    config_path = ROOT / "infra/litellm/config.example.yaml"
    code, result = gateway.run("syntactic", env_path, config_path)
    assert code == 1
    assert result["error"] == {"category": "CONFIG", "code": "LITELLM_MASTER_KEY_INVALID"}
    assert "short" not in json.dumps(result)


def test_dry_run_checks_both_compose_profiles_without_logging_key(tmp_path):
    env_path = tmp_path / ".env"
    key = "sk-" + "x" * 32
    env_path.write_text(
        f"LITELLM_ENABLED=true\nLITELLM_MASTER_KEY={key}\n"
        "OPENBOT_API_KEY=sk-" + "y" * 32 + "\n",
        encoding="utf-8",
    )
    config_path = ROOT / "infra/litellm/config.example.yaml"
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch.object(gateway.subprocess, "run", return_value=completed) as compose:
        code, result = gateway.run("dry-run", env_path, config_path)
    assert code == 0
    assert result["status"] == "pass"
    assert compose.call_count == 2
    assert "--profile" in compose.call_args_list[1].args[0]
    assert key not in json.dumps(result)


def test_dry_run_uses_ephemeral_placeholder_when_optional_gateway_is_disabled(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("LITELLM_ENABLED=false\n", encoding="utf-8")
    config_path = ROOT / "infra/litellm/config.example.yaml"
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch.object(gateway.subprocess, "run", return_value=completed) as compose:
        code, result = gateway.run("dry-run", env_path, config_path)
    assert code == 0
    assert result["status"] == "pass"
    child_env = compose.call_args_list[0].kwargs["env"]
    assert child_env["LITELLM_MASTER_KEY"].startswith("sk-dry-run-only-sentinel-")
    assert "LITELLM_MASTER_KEY" not in gateway.read_env(env_path)


def test_live_categorizes_auth_and_missing_aliases(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LITELLM_ENABLED=true\nLITELLM_MASTER_KEY=sk-" + "x" * 32 + "\n",
        encoding="utf-8",
    )
    config_path = ROOT / "infra/litellm/config.example.yaml"
    with patch.object(gateway, "_get_json", side_effect=gateway.GatewayError("AUTH", "HTTP_401")):
        code, result = gateway.run("live", env_path, config_path)
    assert code == 1
    assert result["error"]["code"] == "HTTP_401"

    def models(url, *, headers=None):
        if url.endswith("/health/liveness"):
            return {"status": "ok"}
        if url.endswith("/v1/models"):
            return {"data": [{"id": "chat"}]}
        return {"models": []}

    with patch.object(gateway, "_get_json", side_effect=models):
        code, result = gateway.run("live", env_path, config_path)
    assert code == 1
    assert result["error"]["code"] == "MODEL_MISSING"


def test_live_network_error_uses_exit_two(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LITELLM_ENABLED=true\nLITELLM_MASTER_KEY=sk-" + "x" * 32 + "\n",
        encoding="utf-8",
    )
    config_path = ROOT / "infra/litellm/config.example.yaml"
    with patch.object(gateway, "_get_json", side_effect=gateway.GatewayError("NETWORK", "NETWORK")):
        code, result = gateway.run("live", env_path, config_path)
    assert code == 2
    assert result["error"] == {"category": "NETWORK", "code": "NETWORK"}
