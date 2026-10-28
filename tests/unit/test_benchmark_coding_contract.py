from __future__ import annotations

from pathlib import Path

from scripts.benchmark_coding import public_fixture


def test_coding_runner_prompt_includes_public_case_but_not_hidden_oracle():
    fixture, prompt = public_fixture(Path("evals/fixtures/bug-cpf/case.json"))
    assert fixture["id"] == "demo-cpf-checksum-v1"
    assert "invalid check digits" in prompt
    assert "services/cpf.py" in prompt
    assert "hidden_test_bundle" not in prompt
    assert "assert is_valid_cpf" not in prompt
    assert "52998224726" not in prompt
