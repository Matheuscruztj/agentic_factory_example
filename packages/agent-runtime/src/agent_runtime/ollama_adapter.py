"""Direct local Ollama chat adapter with bounded output and typed failures."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx


class OllamaError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    tag: str
    digest: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ChatResult:
    model: str
    model_digest: str
    capabilities: tuple[str, ...]
    content: str
    tool_calls: tuple[dict[str, Any], ...]
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ns: int | None


class OllamaAdapter:
    """No cloud fallback or model download; callers share the supplied inference semaphore."""

    def __init__(
        self,
        base_url: str,
        *,
        semaphore: asyncio.Semaphore | None = None,
        slot_provider: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
        timeout_seconds: float = 180,
        max_context: int = 8192,
        max_output: int = 2048,
        recorder: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
        run_id: str | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise OllamaError("INVALID_BASE_URL")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise OllamaError("TLS_REQUIRED")
        if not 1 <= timeout_seconds <= 7200 or not 256 <= max_context <= 131072:
            raise OllamaError("INVALID_MODEL_LIMITS")
        if not 1 <= max_output <= min(max_context, 32768):
            raise OllamaError("INVALID_MODEL_LIMITS")
        self.base_url = base_url.rstrip("/")
        if semaphore is None and slot_provider is None:
            raise OllamaError("INFERENCE_QUEUE_REQUIRED")
        self.semaphore = semaphore
        self.slot_provider = slot_provider
        self.timeout_seconds = timeout_seconds
        self.max_context = max_context
        self.max_output = max_output
        self.recorder = recorder
        self.run_id = run_id

    async def identify(self, model_tag: str) -> ModelIdentity:
        if not model_tag.strip():
            raise OllamaError("MODEL_TAG_REQUIRED")
        payload = await self._request("GET", "/api/tags")
        matches = [
            model
            for model in payload.get("models", [])
            if isinstance(model, dict) and model.get("name") == model_tag
        ]
        if len(matches) != 1:
            raise OllamaError("MODEL_NOT_INSTALLED")
        digest = matches[0].get("digest")
        if not isinstance(digest, str) or not digest:
            raise OllamaError("MODEL_DIGEST_UNAVAILABLE")
        details = await self._request("POST", "/api/show", {"model": model_tag})
        capabilities = details.get("capabilities", [])
        if not isinstance(capabilities, list) or any(
            not isinstance(item, str) for item in capabilities
        ):
            raise OllamaError("MODEL_CAPABILITIES_INVALID")
        return ModelIdentity(model_tag, digest, tuple(sorted(set(capabilities))))

    async def chat(
        self,
        model_tag: str,
        messages: list[dict[str, Any]],
        *,
        format_schema: dict[str, Any] | str | None = None,
        tools: list[dict[str, Any]] | None = None,
        think: bool | str | None = None,
        output_tokens: int | None = None,
    ) -> ChatResult:
        if not messages or any(not isinstance(item, dict) for item in messages):
            raise OllamaError("MESSAGES_REQUIRED")
        max_tokens = output_tokens or self.max_output
        if type(max_tokens) is not int or not 1 <= max_tokens <= self.max_output:
            raise OllamaError("OUTPUT_BUDGET_EXCEEDED")
        payload: dict[str, Any] = {
            "model": model_tag,
            "messages": messages,
            "stream": False,
            "options": {"num_ctx": self.max_context, "num_predict": max_tokens},
        }
        if format_schema is not None:
            if isinstance(format_schema, dict) and not format_schema:
                raise OllamaError("OUTPUT_SCHEMA_INVALID")
            payload["format"] = format_schema
        if think is not None:
            if type(think) is not bool and (not isinstance(think, str) or not think.strip()):
                raise OllamaError("THINKING_MODE_INVALID")
            payload["think"] = think
        if tools is not None:
            if not isinstance(tools, list) or any(not isinstance(item, dict) for item in tools):
                raise OllamaError("TOOLS_INVALID")
            payload["tools"] = tools
        identity = await self.identify(model_tag)
        if self.slot_provider is not None:
            async with self.slot_provider():
                response = await self._request("POST", "/api/chat", payload)
        else:
            async with self.semaphore:
                response = await self._request("POST", "/api/chat", payload)
        message = response.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content", ""), str):
            raise OllamaError("MODEL_RESPONSE_INVALID")
        if isinstance(format_schema, dict) or format_schema == "json":
            try:
                structured = json.loads(message.get("content", ""))
            except json.JSONDecodeError:
                raise OllamaError("OUTPUT_SCHEMA_INVALID") from None
            if not isinstance(structured, dict):
                raise OllamaError("OUTPUT_SCHEMA_INVALID")
        calls = message.get("tool_calls", [])
        if not isinstance(calls, list) or any(not isinstance(call, dict) for call in calls):
            raise OllamaError("TOOL_CALL_SCHEMA_INVALID")
        for call in calls:
            function = call.get("function")
            if (
                not isinstance(function, dict)
                or not isinstance(function.get("name"), str)
                or not isinstance(function.get("arguments", {}), dict)
            ):
                raise OllamaError("TOOL_CALL_SCHEMA_INVALID")
        usage = {
            "run_id": self.run_id,
            "model": model_tag,
            "model_digest": identity.digest,
            "capabilities": list(identity.capabilities),
            "max_context": self.max_context,
            "max_output": max_tokens,
            "prompt_tokens": _optional_int(response.get("prompt_eval_count")),
            "completion_tokens": _optional_int(response.get("eval_count")),
            "duration_ns": _optional_int(response.get("total_duration")),
        }
        if self.recorder:
            try:
                recorded = self.recorder(usage)
                if asyncio.iscoroutine(recorded):
                    await recorded
            except Exception:
                pass
        return ChatResult(
            model_tag,
            identity.digest,
            identity.capabilities,
            message.get("content", ""),
            tuple(calls),
            **usage_without_model(usage),
        )

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.request(method, self.base_url + path, json=body)
                response.raise_for_status()
                value = response.json()
        except httpx.TimeoutException:
            raise OllamaError("MODEL_TIMEOUT") from None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404 and body and body.get("model"):
                raise OllamaError("MODEL_NOT_INSTALLED") from None
            if exc.response.status_code == 500:
                raise OllamaError("MODEL_RUNTIME_ERROR") from None
            raise OllamaError("OLLAMA_UPSTREAM_ERROR") from None
        except (httpx.HTTPError, json.JSONDecodeError):
            raise OllamaError("OLLAMA_UNAVAILABLE") from None
        if not isinstance(value, dict):
            raise OllamaError("OLLAMA_RESPONSE_INVALID")
        if value.get("error"):
            reason = str(value["error"]).casefold()
            if "memory" in reason or "alloc" in reason or "cuda" in reason:
                raise OllamaError("MODEL_OUT_OF_MEMORY")
            if "not found" in reason or "pull" in reason:
                raise OllamaError("MODEL_NOT_INSTALLED")
            raise OllamaError("MODEL_RUNTIME_ERROR")
        return value


def _optional_int(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def usage_without_model(usage: dict[str, Any]) -> dict[str, int | None]:
    return {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "duration_ns")}
