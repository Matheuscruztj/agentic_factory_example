"""Opt-in Telegram long polling with allowlists and post-processing offsets."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TelegramError(RuntimeError):
    pass


class TelegramPoller:
    def __init__(
        self,
        *,
        token: str,
        allowed_chats: set[int],
        allowed_users: set[int],
        enabled: bool = False,
        request: Callable[[str], dict] | None = None,
    ) -> None:
        if not enabled:
            raise TelegramError("TELEGRAM_INTAKE_DISABLED")
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
            raise TelegramError("INVALID_BOT_TOKEN")
        if not allowed_chats or not allowed_users:
            raise TelegramError("ALLOWLIST_REQUIRED")
        self._token = token
        self.allowed_chats = frozenset(allowed_chats)
        self.allowed_users = frozenset(allowed_users)
        self._request = request or self._http

    def _http(self, method: str, params: dict) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        req = Request(
            url,
            data=urlencode(params).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urlopen(req, timeout=40) as response:
                value = json.loads(response.read(1_000_000))
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            raise TelegramError("TELEGRAM_REQUEST_FAILED") from None
        if value.get("ok") is not True:
            raise TelegramError("TELEGRAM_API_ERROR")
        return value

    def poll_once(self, *, offset: int, process: Callable[[dict], None], timeout: int = 25) -> int:
        if offset < 0 or not 0 <= timeout <= 50:
            raise TelegramError("INVALID_POLL_ARGUMENT")
        result = self._request(
            "getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": '["message"]'}
        )
        updates = result.get("result")
        if not isinstance(updates, list):
            raise TelegramError("INVALID_RESPONSE")
        next_offset = offset
        for update in updates:
            if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
                continue
            message = update.get("message")
            if isinstance(message, dict):
                chat_id = message.get("chat", {}).get("id")
                user_id = message.get("from", {}).get("id")
                if chat_id in self.allowed_chats and user_id in self.allowed_users:
                    process(message)
            next_offset = max(next_offset, update["update_id"] + 1)
        return next_offset
