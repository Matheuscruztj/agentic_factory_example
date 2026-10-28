from __future__ import annotations

import asyncio

import httpx
from agent_runtime.ollama_adapter import OllamaAdapter


def test_adapter_records_run_identity_and_budgets(monkeypatch):
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                200,
                json={"models": [{"name": "coder:latest", "digest": "sha256:abc"}]},
            )
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion", "tools"]})
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message": {"content": "ok"}, "eval_count": 3})
        return httpx.Response(404)

    real_client = httpx.AsyncClient

    def mock_client(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", mock_client)

    async def run() -> None:
        adapter = OllamaAdapter(
            "http://127.0.0.1:11434",
            semaphore=asyncio.Semaphore(1),
            max_context=1024,
            max_output=128,
            run_id="run-123",
            recorder=calls.append,
        )
        await adapter.chat("coder:latest", [{"role": "user", "content": "hi"}])

    asyncio.run(run())
    assert calls == [
        {
            "run_id": "run-123",
            "model": "coder:latest",
            "model_digest": "sha256:abc",
            "capabilities": ["completion", "tools"],
            "max_context": 1024,
            "max_output": 128,
            "prompt_tokens": None,
            "completion_tokens": 3,
            "duration_ns": None,
        }
    ]
