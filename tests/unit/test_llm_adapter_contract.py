from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from agent_runtime.llm_adapter import (
    LiteLLMGatewayAdapter,
    LLMAdapter,
    LLMAdapterError,
    OllamaDirectAdapter,
)

MODEL = "qwen3:4b"
DIGEST = "a" * 64
MESSAGES = [{"role": "user", "content": "call the tool"}]
TOOLS = [{"type": "function", "function": {"name": "lookup", "parameters": {"type": "object"}}}]


def test_direct_ollama_complete_normalizes_tools_and_keeps_digest():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert payload["tools"] == TOOLS
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [{"function": {"name": "lookup", "arguments": {"id": 3}}}],
                },
                "prompt_eval_count": 10,
                "eval_count": 2,
            },
        )

    adapter = OllamaDirectAdapter(
        base_url="http://127.0.0.1:11434",
        model_digests={MODEL: DIGEST},
        transport=httpx.MockTransport(handle),
        semaphore=asyncio.Semaphore(1),
    )
    assert isinstance(adapter, LLMAdapter)
    result = asyncio.run(adapter.complete(model_id=MODEL, messages=MESSAGES, tools=TOOLS))
    assert result.model_digest == DIGEST
    assert result.tool_calls == ({"name": "lookup", "arguments": {"id": 3}},)
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 2


def test_litellm_complete_normalizes_openai_tool_calls_and_auth():
    key = "sk-" + "x" * 32

    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {key}"
        assert request.headers["x-task-id"] == "task_123"
        assert request.headers["x-correlation-id"] == "corr-abc"
        payload = json.loads(request.content)
        assert payload["tools"] == TOOLS
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "lookup",
                                        "arguments": '{"id":3}',
                                    }
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    adapter = LiteLLMGatewayAdapter(
        base_url="http://127.0.0.1:4000",
        api_key=key,
        model_digests={"chat": DIGEST},
        transport=httpx.MockTransport(handle),
        semaphore=asyncio.Semaphore(1),
        task_id="task_123",
        correlation_id="corr-abc",
    )
    assert isinstance(adapter, LLMAdapter)
    result = asyncio.run(adapter.complete(model_id="chat", messages=MESSAGES, tools=TOOLS))
    assert result.model_digest == DIGEST
    assert result.tool_calls == ({"name": "lookup", "arguments": {"id": 3}},)
    assert result.prompt_tokens == 10


@pytest.mark.parametrize("gateway", [False, True])
def test_streaming_normalizes_text_and_tool_call_frames(gateway: bool):
    key = "sk-" + "x" * 32
    if gateway:
        frames = [
            "data: "
            + json.dumps({"choices": [{"delta": {"content": "hello"}}]})
            + "\n",
            "data: "
            + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "name": "lookup",
                                            "arguments": '{"id":',
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            )
            + "\n",
            "data: [DONE]\n",
        ]
        adapter = LiteLLMGatewayAdapter(
            base_url="http://127.0.0.1:4000",
            api_key=key,
            model_digests={"chat": DIGEST},
            semaphore=asyncio.Semaphore(1),
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, text="".join(frames))
            ),
        )
        model = "chat"
    else:
        frames = [
            '{"message":{"content":"hello"},"done":false}\n',
            '{"message":{"tool_calls":[{"function":{"name":"lookup","arguments":{"id":3}}}]},"done":false}\n',
            '{"message":{"content":""},"done":true}\n',
        ]
        adapter = OllamaDirectAdapter(
            base_url="http://127.0.0.1:11434",
            model_digests={MODEL: DIGEST},
            semaphore=asyncio.Semaphore(1),
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, text="".join(frames))
            ),
        )
        model = MODEL

    async def collect():
        return [
            chunk
            async for chunk in adapter.stream(
                model_id=model, messages=MESSAGES, tools=TOOLS
            )
        ]

    chunks = asyncio.run(collect())
    assert chunks[0].content == "hello"
    assert chunks[-1].done is True
    if gateway:
        assert chunks[1].tool_calls == (
            {"index": 0, "name": "lookup", "arguments_delta": '{"id":'},
        )
    else:
        assert chunks[1].tool_calls == ({"name": "lookup", "arguments": {"id": 3}},)


def test_gateway_failure_does_not_fallback_to_direct_ollama():
    def unavailable(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic gateway outage")

    adapter = LiteLLMGatewayAdapter(
        base_url="http://127.0.0.1:4000",
        api_key="sk-" + "x" * 32,
        model_digests={"chat": DIGEST},
        semaphore=asyncio.Semaphore(1),
        transport=httpx.MockTransport(unavailable),
    )
    with pytest.raises(LLMAdapterError, match="MODEL_UNAVAILABLE"):
        asyncio.run(adapter.complete(model_id="chat", messages=MESSAGES))


def test_adapters_require_a_shared_inference_slot():
    with pytest.raises(LLMAdapterError, match="INFERENCE_QUEUE_REQUIRED"):
        OllamaDirectAdapter(base_url="http://127.0.0.1:11434", model_digests={MODEL: DIGEST})


def test_adapter_rejects_injection_in_task_context():
    with pytest.raises(LLMAdapterError, match="TASK_ID_INVALID"):
        OllamaDirectAdapter(
            base_url="http://127.0.0.1:11434",
            model_digests={MODEL: DIGEST},
            semaphore=asyncio.Semaphore(1),
            task_id="x\r\nAuthorization: Bearer secret",
        )
