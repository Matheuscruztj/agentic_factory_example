"""Pinned OpenBot v1 transport boundary; no shell or filesystem tools are exposed here."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Protocol
from urllib.parse import urlencode, urlsplit

import httpx


class OpenBotError(RuntimeError):
    pass


class OpenBotTransport(Protocol):
    def request(
        self, method: str, path: str, *, body: dict | None = None, query: dict | None = None
    ) -> dict: ...


class HttpOpenBotTransport:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 10) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise OpenBotError("INVALID_BASE_URL")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise OpenBotError("TLS_REQUIRED")
        if not api_key:
            raise OpenBotError("API_KEY_REQUIRED")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def request(
        self, method: str, path: str, *, body: dict | None = None, query: dict | None = None
    ) -> dict:
        if not re.fullmatch(
            r"/api/v1/(?:threads(?:/[A-Za-z0-9_-]+(?:/messages)?)?|runs/[A-Za-z0-9_-]+/cancel)",
            path,
        ):
            raise OpenBotError("ENDPOINT_NOT_ALLOWED")
        url = self._base_url + path
        if query:
            url += "?" + urlencode(query)
        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "X-API-Key": self._api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            with httpx.stream(
                method,
                url,
                content=data,
                headers=headers,
                timeout=self._timeout,
                follow_redirects=False,
            ) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_bytes():
                    if len(payload) + len(chunk) > 1_000_000:
                        raise OpenBotError("INVALID_RESPONSE")
                    payload.extend(chunk)
                value = json.loads(payload)
        except httpx.HTTPStatusError as exc:
            reason = {
                401: "AUTHENTICATION_FAILED",
                403: "PERMISSION_DENIED",
                404: "NOT_FOUND",
                409: "CONFLICT",
                429: "RATE_LIMITED",
            }.get(exc.response.status_code, "UPSTREAM_ERROR")
            raise OpenBotError(reason) from None
        except httpx.HTTPError:
            raise OpenBotError("NETWORK_ERROR") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise OpenBotError("INVALID_RESPONSE") from None
        if not isinstance(value, dict):
            raise OpenBotError("INVALID_RESPONSE")
        return value


class OpenBotAdapter:
    """Internal contract mapped to the documented OpenBot /api/v1 endpoints."""

    def __init__(self, transport: OpenBotTransport) -> None:
        self._transport = transport

    def create_thread(
        self,
        *,
        title: str,
        bot_handle: str,
        external_actor: str = "you",
        working_directory: str | None = None,
    ) -> str:
        actor = _safe_handle(bot_handle)
        external = _safe_handle(external_actor)
        if not title.strip():
            raise OpenBotError("INVALID_THREAD_INPUT")
        body = {
            "title": title[:240],
            "handles": [external, actor],
            "default_bot_handle": actor,
        }
        if working_directory is not None:
            body["working_directory"] = _safe_working_directory(working_directory)
        result = self._transport.request(
            "POST",
            "/api/v1/threads",
            body=body,
        )
        thread = result.get("thread", result)
        thread_id = thread.get("id") if isinstance(thread, dict) else None
        if not isinstance(thread_id, str) or not thread_id:
            raise OpenBotError("INVALID_THREAD_RESPONSE")
        return thread_id

    def find_thread(self, thread_id: str) -> dict:
        result = self._transport.request("GET", f"/api/v1/threads/{_safe_id(thread_id)}")
        thread = result.get("thread", result)
        if not isinstance(thread, dict) or not isinstance(thread.get("id"), str):
            raise OpenBotError("INVALID_THREAD_RESPONSE")
        if thread.get("id") != thread_id:
            raise OpenBotError("INVALID_THREAD_RESPONSE")
        return {
            "thread": thread,
            **{key: value for key, value in result.items() if key != "thread"},
        }

    def send_message(self, thread_id: str, *, content: str, recipient: str) -> str:
        recipient_handle = _safe_handle(recipient)
        if not content.strip():
            raise OpenBotError("INVALID_MESSAGE")
        result = self._transport.request(
            "POST",
            f"/api/v1/threads/{_safe_id(thread_id)}/messages",
            body={"content": content[:20_000], "to": [recipient_handle], "from": "you"},
        )
        message = result.get("message")
        message_id = message.get("id") if isinstance(message, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise OpenBotError("INVALID_MESSAGE_RESPONSE")
        return message_id

    def poll_events(self, thread_id: str, *, before: str | None = None, limit: int = 100) -> dict:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise OpenBotError("INVALID_PAGE")
        query = {"limit": str(limit)}
        if before:
            query["before"] = _safe_id(before)
        return self._transport.request("GET", f"/api/v1/threads/{_safe_id(thread_id)}", query=query)

    def cancel(self, run_id: str) -> dict:
        return self._transport.request("POST", f"/api/v1/runs/{_safe_id(run_id)}/cancel", body={})


def _safe_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise OpenBotError("INVALID_UPSTREAM_ID")
    return value


def _safe_handle(value: str) -> str:
    handle = value.removeprefix("@") if isinstance(value, str) else ""
    if not re.fullmatch(r"[a-z0-9_-]{2,32}", handle):
        raise OpenBotError("INVALID_BOT_HANDLE")
    return handle


def _safe_working_directory(value: str) -> str:
    """Accept only a relative workspace path; OpenBot enforces its root boundary."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 200
        or "\\" in value
        or "\x00" in value
    ):
        raise OpenBotError("INVALID_WORKING_DIRECTORY")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise OpenBotError("INVALID_WORKING_DIRECTORY")
    return path.as_posix()
