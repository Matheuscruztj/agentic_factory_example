"""Common local LLM contract for direct Ollama and the optional LiteLLM gateway."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlsplit

import httpx
from observability.tracing import model_span  # type: ignore[import-untyped]


class LLMAdapterError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ChatResult:
    model_id: str
    model_digest: str
    content: str
    tool_calls: tuple[dict[str, Any], ...]
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ChatChunk:
    content: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    done: bool = False


@runtime_checkable
class LLMAdapter(Protocol):
    async def complete(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | str | None = None,
    ) -> ChatResult: ...

    def stream(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | str | None = None,
    ) -> AsyncIterator[ChatChunk]: ...


def validate_task_context(
    *, task_id: str | None, correlation_id: str | None
) -> tuple[str | None, str | None]:
    """Validate identifiers before they are attached to telemetry or gateway headers."""
    if task_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
        raise LLMAdapterError("TASK_ID_INVALID")
    if correlation_id is not None and not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,128}", correlation_id
    ):
        raise LLMAdapterError("CORRELATION_ID_INVALID")
    return task_id, correlation_id


class _LocalHTTPAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None,
        semaphore: Any | None,
        slot_provider: Callable[[], AbstractAsyncContextManager[Any]] | None,
        task_id: str | None,
        correlation_id: str | None,
        telemetry: bool,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise LLMAdapterError("LOCAL_ENDPOINT_REQUIRED")
        if not 1 <= timeout_seconds <= 7200:
            raise LLMAdapterError("TIMEOUT_INVALID")
        if semaphore is None and slot_provider is None:
            raise LLMAdapterError("INFERENCE_QUEUE_REQUIRED")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.semaphore = semaphore
        self.slot_provider = slot_provider
        self.task_id, self.correlation_id = validate_task_context(
            task_id=task_id, correlation_id=correlation_id
        )
        self.telemetry = telemetry

    def _span(self, model_id: str):
        if not self.telemetry:
            from contextlib import nullcontext

            return nullcontext()
        return model_span(
            model_id,
            correlation_id=self.correlation_id or "local",
            task_id=self.task_id,
            provider="litellm" if isinstance(self, LiteLLMGatewayAdapter) else "ollama",
        )

    def _context_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.task_id:
            headers["x-task-id"] = self.task_id
        if self.correlation_id:
            headers["x-correlation-id"] = self.correlation_id
        return headers

    @asynccontextmanager
    async def _slot(self) -> AsyncIterator[None]:
        if self.slot_provider is not None:
            async with self.slot_provider():
                yield
        else:
            assert self.semaphore is not None
            async with self.semaphore:
                yield

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
            trust_env=False,
        )

    async def _json(self, path: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
        try:
            async with self._client() as client:
                response = await client.post(self.base_url + path, json=payload, headers=headers)
                response.raise_for_status()
                value = response.json()
        except httpx.TimeoutException:
            raise LLMAdapterError("MODEL_TIMEOUT") from None
        except httpx.HTTPStatusError as exc:
            code = "HTTP_401" if exc.response.status_code in {401, 403} else "UPSTREAM_ERROR"
            raise LLMAdapterError(code) from None
        except (httpx.HTTPError, json.JSONDecodeError):
            raise LLMAdapterError("MODEL_UNAVAILABLE") from None
        if not isinstance(value, dict):
            raise LLMAdapterError("MODEL_RESPONSE_INVALID")
        return value

    async def _lines(
        self, path: str, payload: dict, headers: dict[str, str] | None = None
    ) -> AsyncIterator[str]:
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST", self.base_url + path, json=payload, headers=headers
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        yield line
        except httpx.TimeoutException:
            raise LLMAdapterError("MODEL_TIMEOUT") from None
        except httpx.HTTPStatusError as exc:
            code = "HTTP_401" if exc.response.status_code in {401, 403} else "UPSTREAM_ERROR"
            raise LLMAdapterError(code) from None
        except httpx.HTTPError:
            raise LLMAdapterError("MODEL_UNAVAILABLE") from None


class OllamaDirectAdapter(_LocalHTTPAdapter):
    """Direct Ollama adapter; it never redirects to LiteLLM or a cloud provider."""

    def __init__(
        self,
        *,
        base_url: str,
        model_digests: dict[str, str],
        timeout_seconds: float = 180,
        transport: httpx.AsyncBaseTransport | None = None,
        semaphore: Any | None = None,
        slot_provider: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
        task_id: str | None = None,
        correlation_id: str | None = None,
        telemetry: bool = False,
    ) -> None:
        super().__init__(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
            semaphore=semaphore,
            slot_provider=slot_provider,
            task_id=task_id,
            correlation_id=correlation_id,
            telemetry=telemetry,
        )
        if not model_digests or any(not key or not value for key, value in model_digests.items()):
            raise LLMAdapterError("MODEL_DIGEST_REQUIRED")
        self.model_digests = dict(model_digests)

    def _payload(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        format_schema: dict[str, Any] | str | None,
        stream: bool,
    ) -> dict:
        if model_id not in self.model_digests:
            raise LLMAdapterError("MODEL_ID_UNBOUND")
        if not messages or any(not isinstance(item, dict) for item in messages):
            raise LLMAdapterError("MESSAGES_REQUIRED")
        payload: dict[str, Any] = {"model": model_id, "messages": messages, "stream": stream}
        if tools is not None:
            if any(not isinstance(tool, dict) for tool in tools):
                raise LLMAdapterError("TOOLS_INVALID")
            payload["tools"] = tools
        if format_schema is not None:
            payload["format"] = format_schema
        return payload

    async def complete(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | str | None = None,
    ) -> ChatResult:
        payload = self._payload(
            model_id=model_id,
            messages=messages,
            tools=tools,
            format_schema=format_schema,
            stream=False,
        )
        async with self._slot():
            with self._span(model_id):
                response = await self._json("/api/chat", payload, self._context_headers())
        message = response.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content", ""), str):
            raise LLMAdapterError("MODEL_RESPONSE_INVALID")
        calls = _tool_calls(message.get("tool_calls", []))
        return ChatResult(
            model_id,
            self.model_digests[model_id],
            message.get("content", ""),
            calls,
            _int_or_none(response.get("prompt_eval_count")),
            _int_or_none(response.get("eval_count")),
        )

    async def stream(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        payload = self._payload(
            model_id=model_id,
            messages=messages,
            tools=tools,
            format_schema=format_schema,
            stream=True,
        )
        async with self._slot():
            with self._span(model_id):
              async for line in self._lines("/api/chat", payload, self._context_headers()):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    raise LLMAdapterError("STREAM_FRAME_INVALID") from None
                if not isinstance(value, dict):
                    raise LLMAdapterError("STREAM_FRAME_INVALID")
                message = value.get("message", {})
                if not isinstance(message, dict):
                    raise LLMAdapterError("MODEL_RESPONSE_INVALID")
                yield ChatChunk(
                    content=message.get("content", ""),
                    tool_calls=_tool_calls(message.get("tool_calls", [])),
                    done=value.get("done") is True,
                )


class LiteLLMGatewayAdapter(_LocalHTTPAdapter):
    """OpenAI-compatible local gateway adapter; missing gateway never falls back."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_digests: dict[str, str],
        timeout_seconds: float = 180,
        transport: httpx.AsyncBaseTransport | None = None,
        semaphore: Any | None = None,
        slot_provider: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
        task_id: str | None = None,
        correlation_id: str | None = None,
        telemetry: bool = False,
    ) -> None:
        super().__init__(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            transport=transport,
            semaphore=semaphore,
            slot_provider=slot_provider,
            task_id=task_id,
            correlation_id=correlation_id,
            telemetry=telemetry,
        )
        if not api_key.startswith("sk-") or len(api_key) < 27:
            raise LLMAdapterError("GATEWAY_KEY_INVALID")
        if not model_digests or any(not key or not value for key, value in model_digests.items()):
            raise LLMAdapterError("MODEL_DIGEST_REQUIRED")
        self.api_key = api_key
        self.model_digests = dict(model_digests)

    def _payload(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        format_schema: dict[str, Any] | str | None,
        stream: bool,
    ) -> dict:
        if model_id not in self.model_digests:
            raise LLMAdapterError("MODEL_ID_UNBOUND")
        if not messages or any(not isinstance(item, dict) for item in messages):
            raise LLMAdapterError("MESSAGES_REQUIRED")
        payload: dict[str, Any] = {"model": model_id, "messages": messages, "stream": stream}
        if tools is not None:
            if any(not isinstance(tool, dict) for tool in tools):
                raise LLMAdapterError("TOOLS_INVALID")
            payload["tools"] = tools
        if format_schema == "json":
            payload["response_format"] = {"type": "json_object"}
        elif isinstance(format_schema, dict):
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True, "schema": format_schema},
            }
        return payload

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            **self._context_headers(),
        }

    async def complete(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | str | None = None,
    ) -> ChatResult:
        payload = self._payload(
            model_id=model_id,
            messages=messages,
            tools=tools,
            format_schema=format_schema,
            stream=False,
        )
        async with self._slot():
            with self._span(model_id):
                response = await self._json("/v1/chat/completions", payload, self._headers())
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise LLMAdapterError("MODEL_RESPONSE_INVALID") from None
        if not isinstance(message, dict) or not isinstance(message.get("content") or "", str):
            raise LLMAdapterError("MODEL_RESPONSE_INVALID")
        calls = _tool_calls(message.get("tool_calls", []))
        usage = response.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        return ChatResult(
            model_id,
            self.model_digests[model_id],
            message.get("content") or "",
            calls,
            _int_or_none(usage.get("prompt_tokens")),
            _int_or_none(usage.get("completion_tokens")),
        )

    async def stream(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        format_schema: dict[str, Any] | str | None = None,
    ) -> AsyncIterator[ChatChunk]:
        payload = self._payload(
            model_id=model_id,
            messages=messages,
            tools=tools,
            format_schema=format_schema,
            stream=True,
        )
        async with self._slot():
            async for line in self._lines(
                "/v1/chat/completions", payload, self._headers()
            ):
                if not line.startswith("data:"):
                    continue
                content = line[5:].strip()
                if content == "[DONE]":
                    yield ChatChunk(done=True)
                    return
                try:
                    value = json.loads(content)
                    delta = value["choices"][0]["delta"]
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    raise LLMAdapterError("STREAM_FRAME_INVALID") from None
                if not isinstance(delta, dict):
                    raise LLMAdapterError("STREAM_FRAME_INVALID")
                yield ChatChunk(
                    content=delta.get("content") or "",
                    tool_calls=_tool_calls(delta.get("tool_calls", []), allow_partial=True),
                )


def _tool_calls(value: Any, *, allow_partial: bool = False) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or any(not isinstance(call, dict) for call in value):
        raise LLMAdapterError("TOOL_CALL_SCHEMA_INVALID")
    output = []
    for call in value:
        function = call.get("function", {})
        if not isinstance(function, dict):
            raise LLMAdapterError("TOOL_CALL_SCHEMA_INVALID")
        name = function.get("name")
        arguments = function.get("arguments", {})
        if allow_partial and isinstance(arguments, str):
            output.append(
                {"index": call.get("index", 0), "name": name, "arguments_delta": arguments}
            )
            continue
        if not isinstance(name, str) or not isinstance(arguments, dict):
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    raise LLMAdapterError("TOOL_CALL_SCHEMA_INVALID") from None
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise LLMAdapterError("TOOL_CALL_SCHEMA_INVALID")
        output.append({"name": name, "arguments": arguments})
    return tuple(output)


def _int_or_none(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None
