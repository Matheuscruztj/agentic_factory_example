"""Opt-in Telegram long polling with allowlists and post-processing offsets."""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass

import httpx


class TelegramError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TelegramCommand:
    grammar_version: int
    action: str
    reference: str | None = None
    question_id: str | None = None
    persona: str | None = None
    text: str | None = None
    approval_id: str | None = None
    payload_hash: str | None = None


_COMMAND_ALIASES = {
    "demanda": "demand",
    "d": "demand",
    "status": "status",
    "s": "status",
    "progresso": "status",
    "approvals": "approvals",
    "aprovacoes": "approvals",
    "aprovações": "approvals",
    "approve": "approve",
    "aprovar": "approve",
    "aprova": "approve",
    "reject": "reject",
    "rejeitar": "reject",
    "rejeita": "reject",
    "responder": "reply",
    "reply": "reply",
    "r": "reply",
    "agente": "agent",
    "agent": "agent",
    "a": "agent",
    "cancelar": "cancel",
    "cancel": "cancel",
    "c": "cancel",
    "ajuda": "help",
    "help": "help",
    "start": "help",
}
_PERSONAS = {"analyst", "planner", "backend", "frontend", "qa", "reviewer"}
_OUTBOUND_REDACTIONS = (
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\w)\+?\d[\d ().-]{7,}\d(?!\w)"),
)


def redact_telegram_text(text: str, *, max_length: int = 4096) -> str:
    """Redact likely secrets/PII and bound text before storing or sending it."""
    if not isinstance(text, str) or not text.strip():
        raise TelegramError("MESSAGE_TEXT_REQUIRED")
    if type(max_length) is not int or not 1 <= max_length <= 4096:
        raise TelegramError("INVALID_MESSAGE_LIMIT")
    safe = text.strip()
    for pattern in _OUTBOUND_REDACTIONS:
        safe = pattern.sub("[REDACTED]", safe)
    if len(safe) > max_length:
        safe = safe[: max_length - 1] + "…"
    return safe


def parse_telegram_command(text: str) -> TelegramCommand:
    """Parse grammar v1; ordinary text remains a demand and never an approval."""
    if not isinstance(text, str) or not text.strip() or len(text) > 20_000:
        raise TelegramError("MESSAGE_TEXT_REQUIRED")
    content = text.strip()
    if not content.startswith("/"):
        return TelegramCommand(1, "demand", text=content)
    command_word = content.split(maxsplit=1)[0]
    if not re.fullmatch(r"/[A-Za-z_][A-Za-z0-9_]*(?:@[A-Za-z0-9_]+)?", command_word):
        raise TelegramError("COMMAND_SYNTAX_INVALID")
    name = command_word[1:].split("@", 1)[0].casefold()
    action = _COMMAND_ALIASES.get(name)
    if action is None:
        raise TelegramError("COMMAND_UNKNOWN")
    if action == "demand":
        body = content.split(maxsplit=1)[1].strip() if len(content.split(maxsplit=1)) > 1 else ""
        if not body:
            raise TelegramError("DEMAND_TEXT_REQUIRED")
        return TelegramCommand(1, action, text=body)
    try:
        parts = shlex.split(content, posix=True)
    except ValueError:
        raise TelegramError("COMMAND_SYNTAX_INVALID") from None
    args = parts[1:]
    if action == "help":
        if args:
            raise TelegramError("COMMAND_ARGUMENTS_INVALID")
        return TelegramCommand(1, action)
    if action == "approvals":
        if args:
            raise TelegramError("COMMAND_ARGUMENTS_INVALID")
        return TelegramCommand(1, action)
    if action in {"approve", "reject"}:
        if (
            len(args) != 2
            or not re.fullmatch(
                r"[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-"
                r"[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}",
                args[0],
            )
            or not re.fullmatch(r"[a-fA-F0-9]{64}", args[1])
        ):
            raise TelegramError("APPROVAL_SYNTAX_INVALID")
        return TelegramCommand(
            1,
            action,
            approval_id=args[0],
            payload_hash=args[1].lower(),
        )
    if action in {"status", "cancel"}:
        if len(args) != 1 or not re.fullmatch(r"(?:DEMAND|TASK)-[A-Za-z0-9-]{8,64}", args[0], re.I):
            raise TelegramError("DEMAND_REFERENCE_REQUIRED")
        return TelegramCommand(1, action, reference=args[0].upper())
    if action == "reply":
        raw_parts = content.split(maxsplit=3)
        if len(raw_parts) < 4:
            raise TelegramError("REPLY_SYNTAX_INVALID")
        _, reference, question_id, reply = raw_parts
        if not re.fullmatch(r"(?:DEMAND|TASK)-[A-Za-z0-9-]{8,64}", reference, re.I):
            raise TelegramError("REPLY_SYNTAX_INVALID")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", question_id):
            raise TelegramError("QUESTION_REFERENCE_INVALID")
        if not reply:
            raise TelegramError("REPLY_TEXT_REQUIRED")
        return TelegramCommand(1, action, reference.upper(), question_id, text=reply)
    if action == "agent":
        raw_parts = content.split(maxsplit=3)
        if len(raw_parts) < 4:
            raise TelegramError("AGENT_SYNTAX_INVALID")
        _, reference, raw_persona, message = raw_parts
        if not re.fullmatch(r"(?:DEMAND|TASK)-[A-Za-z0-9-]{8,64}", reference, re.I):
            raise TelegramError("AGENT_SYNTAX_INVALID")
        persona = raw_persona.removeprefix("@").casefold()
        if persona not in _PERSONAS:
            raise TelegramError("PERSONA_NOT_AVAILABLE")
        if not message:
            raise TelegramError("AGENT_MESSAGE_REQUIRED")
        return TelegramCommand(1, action, reference.upper(), persona=persona, text=message)
    raise TelegramError("COMMAND_UNKNOWN")


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
        if not isinstance(token, str) or not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
            raise TelegramError("INVALID_BOT_TOKEN")
        if (
            not allowed_chats
            or not allowed_users
            or any(type(item) is not int for item in allowed_chats | allowed_users)
        ):
            raise TelegramError("ALLOWLIST_REQUIRED")
        self._token = token
        self.allowed_chats = frozenset(allowed_chats)
        self.allowed_users = frozenset(allowed_users)
        self._request = request or self._http

    def _http(self, method: str, params: dict) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        try:
            response = httpx.post(
                url,
                data=params,
                timeout=40,
                follow_redirects=False,
                trust_env=False,
            )
            value = response.json()
        except (httpx.HTTPError, ValueError, UnicodeDecodeError):
            raise TelegramError("TELEGRAM_REQUEST_FAILED") from None
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise TelegramError("TELEGRAM_API_ERROR")
        return value

    def poll_once(
        self,
        *,
        offset: int,
        process: Callable[[dict], None],
        timeout: int = 25,
        persist_offset: Callable[[int], None] | None = None,
    ) -> int:
        if (
            type(offset) is not int
            or type(timeout) is not int
            or offset < 0
            or not 0 <= timeout <= 50
        ):
            raise TelegramError("INVALID_POLL_ARGUMENT")
        result = self._request(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": '["message","edited_message"]',
            },
        )
        updates = result.get("result")
        if not isinstance(updates, list):
            raise TelegramError("INVALID_RESPONSE")
        next_offset = offset
        for update in updates:
            if not isinstance(update, dict) or type(update.get("update_id")) is not int:
                continue
            message = update.get("message", update.get("edited_message"))
            if isinstance(message, dict):
                chat = message.get("chat")
                sender = message.get("from")
                chat_id = chat.get("id") if isinstance(chat, dict) else None
                user_id = sender.get("id") if isinstance(sender, dict) else None
                if chat_id in self.allowed_chats and user_id in self.allowed_users:
                    process(
                        {
                            **message,
                            "_update_id": update["update_id"],
                            "_edited": "edited_message" in update,
                        }
                    )
            next_offset = max(next_offset, update["update_id"] + 1)
        if persist_offset is not None:
            persist_offset(next_offset)
        return next_offset


class TelegramNotifier:
    """Opt-in bounded sender restricted to approved chats; attachments are unsupported."""

    def __init__(
        self,
        *,
        token: str,
        allowed_chats: set[int],
        enabled: bool = False,
        request: Callable[[str, dict], dict] | None = None,
        max_length: int = 4096,
    ) -> None:
        if not enabled:
            raise TelegramError("TELEGRAM_SEND_DISABLED")
        if not isinstance(token, str) or not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", token):
            raise TelegramError("INVALID_BOT_TOKEN")
        if not allowed_chats or any(type(chat) is not int for chat in allowed_chats):
            raise TelegramError("ALLOWLIST_REQUIRED")
        if type(max_length) is not int or not 1 <= max_length <= 4096:
            raise TelegramError("INVALID_MESSAGE_LIMIT")
        self._token = token
        self._allowed_chats = frozenset(allowed_chats)
        self._request = request
        self._max_length = max_length

    def send_message(
        self, *, chat_id: int, text: str, reply_to_message_id: int | None = None
    ) -> dict:
        if type(chat_id) is not int or chat_id not in self._allowed_chats:
            raise TelegramError("CHAT_NOT_ALLOWED")
        safe = redact_telegram_text(text, max_length=self._max_length)
        if reply_to_message_id is not None and (
            type(reply_to_message_id) is not int or reply_to_message_id < 1
        ):
            raise TelegramError("REPLY_REFERENCE_INVALID")
        params: dict[str, object] = {"chat_id": chat_id, "text": safe}
        if reply_to_message_id is not None:
            params["reply_to_message_id"] = reply_to_message_id
        if self._request is None:
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            try:
                response = httpx.post(
                    url,
                    data=params,
                    timeout=20,
                    follow_redirects=False,
                    trust_env=False,
                )
                try:
                    value = response.json()
                except (ValueError, UnicodeDecodeError):
                    raise TelegramError("TELEGRAM_API_ERROR") from None
                if response.status_code == 429:
                    raise TelegramError("TELEGRAM_RATE_LIMITED")
                if response.is_error:
                    raise TelegramError("TELEGRAM_SEND_FAILED")
            except TelegramError:
                raise
            except httpx.HTTPError:
                raise TelegramError("TELEGRAM_SEND_FAILED") from None
        else:
            value = self._request("sendMessage", params)
        if not isinstance(value, dict):
            raise TelegramError("TELEGRAM_API_ERROR")
        if value.get("ok") is not True:
            error_code = value.get("error_code")
            raise TelegramError(
                "TELEGRAM_RATE_LIMITED" if error_code == 429 else "TELEGRAM_API_ERROR"
            )
        result = value.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if type(message_id) is not int:
            raise TelegramError("TELEGRAM_SEND_RESPONSE_INVALID")
        return {"chat_id": chat_id, "message_id": message_id, "redacted": safe != text.strip()}


def telegram_message_to_intake(message: dict) -> dict[str, str]:
    """Map one authorized Telegram message to the shared external-intake shape."""
    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        raise TelegramError("INVALID_MESSAGE")
    chat_id, message_id = chat.get("id"), message.get("message_id")
    if type(chat_id) is not int or type(message_id) is not int:
        raise TelegramError("INVALID_MESSAGE_ID")
    if type(sender.get("id")) is not int:
        raise TelegramError("INVALID_USER_ID")
    raw_content = message.get("text") or message.get("caption")
    if not isinstance(raw_content, str) or not raw_content.strip():
        raise TelegramError("MESSAGE_TEXT_REQUIRED")
    command = parse_telegram_command(raw_content)
    if command.action != "demand":
        raise TelegramError("TELEGRAM_COMMAND_REQUIRES_DISPATCH")
    content = command.text or ""
    title = next((line.strip() for line in content.splitlines() if line.strip()), "")[:240]
    username = sender.get("username")
    author = str(username) if isinstance(username, str) and username.strip() else str(sender["id"])
    return {
        "source": "telegram",
        "external_id": f"{chat_id}:{message_id}",
        "author": author[:160],
        "title": title,
        "text": content[:20000],
        "demand_type": "question",
    }
