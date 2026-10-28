from pathlib import Path


def test_runbook_documents_gateway_offline_diagnostics_and_explicit_direct_mode():
    text = Path("docs/litellm-runbook.md").read_text(encoding="utf-8")
    for fragment in (
        "--mode syntactic",
        "--mode dry-run",
        "--mode live",
        "OllamaAdapter",
        "LiteLLMGatewayAdapter",
        "MODEL_MISSING",
        "OOM",
        "scripts/compare_gateway.py",
        "Não há fallback automático",
        "Prova de independência do modo direct",
    ):
        assert fragment in text
