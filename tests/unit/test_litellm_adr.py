from pathlib import Path


def test_litellm_adr_keeps_direct_mode_and_has_pinned_image_identity():
    adr = Path("docs/adr/ADR-12-litellm-gateway-opt-in.md").read_text(encoding="utf-8")
    assert "direct Ollama adapter as the default" in adr
    assert "There is no automatic direct-to-proxy or" in adr
    assert "ghcr.io/berriai/litellm:v1.106.4@sha256:" in adr
    assert "c169fb3adc514fcf210377c203f3de406d54f10bfdacf13948a4a839db9af7de" in adr
    assert "Current local model inventory" in adr
    assert "Non-goals" in adr
