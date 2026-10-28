from __future__ import annotations

import re
from pathlib import Path

import yaml


def test_litellm_compose_is_opt_in_internal_and_digest_pinned():
    compose = yaml.safe_load(Path("infra/compose/litellm.yml").read_text(encoding="utf-8"))
    service = compose["services"]["litellm"]
    assert service["profiles"] == ["litellm"]
    assert "ports" not in service
    assert service["networks"] == ["agent_backplane"]
    assert re.fullmatch(
        r"ghcr\.io/berriai/litellm:v\d+\.\d+\.\d+@sha256:[0-9a-f]{64}",
        service["image"],
    )
    assert service["environment"]["LITELLM_OFFLINE_MODE"] == "true"
    assert service["environment"]["LITELLM_LOCAL_MODEL_COST_MAP"] == "true"
    assert service["environment"]["LITELLM_MASTER_KEY"].startswith("${LITELLM_MASTER_KEY:?")


def test_litellm_config_declares_only_local_model_aliases():
    config = yaml.safe_load(Path("infra/litellm/config.example.yaml").read_text(encoding="utf-8"))
    assert [model["model_name"] for model in config["model_list"]] == ["chat", "coding", "judge"]
    assert all(
        model["litellm_params"]["api_base"] == "http://ollama:11434"
        for model in config["model_list"]
    )
    assert all(
        model["litellm_params"]["model"].startswith("ollama_chat/")
        for model in config["model_list"]
    )
    assert config["general_settings"]["master_key"] == "os.environ/LITELLM_MASTER_KEY"
