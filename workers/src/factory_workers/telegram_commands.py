"""Telegram status commands and authenticated UI fallback for approvals."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from integrations.telegram import TelegramCommand
from task_engine.models import Demand, Task

from factory_workers.telegram_outbox import enqueue_telegram_message


def _reply(session: Any, message: dict, text: str) -> None:
    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    update_id = message.get("_update_id")
    if type(chat_id) is not int or type(message_id) is not int or type(update_id) is not int:
        raise ValueError("TELEGRAM_MESSAGE_ID_INVALID")
    enqueue_telegram_message(
        session,
        event_id=f"telegram-command-response:{update_id}",
        chat_id=chat_id,
        reply_to_message_id=message_id,
        text=text,
    )


def _actor(message: dict, allowed_user_ids: frozenset[int]) -> str:
    sender = message.get("from") if isinstance(message.get("from"), dict) else {}
    user_id = sender.get("id")
    if type(user_id) is not int or user_id not in allowed_user_ids:
        raise PermissionError("TELEGRAM_OPERATOR_NOT_ALLOWED")
    return f"telegram:{user_id}"


def telegram_command_handler(
    allowed_user_ids: set[int] | frozenset[int], *, ui_url: str | None = None
):
    """Return the intake callback; Telegram identity is not operator identity.

    Sensitive approval details and decisions stay in the authenticated Factory UI
    until an explicit identity-equivalence policy is approved.
    """
    allowlist = frozenset(allowed_user_ids)
    approval_url = ui_url or "http://localhost:5173/?tab=approvals"
    parsed_url = urlsplit(approval_url)
    if (
        parsed_url.scheme not in {"http", "https"}
        or not parsed_url.netloc
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise ValueError("TELEGRAM_APPROVAL_UI_URL_INVALID")

    def handle(session: Any, message: dict, command: TelegramCommand) -> dict:
        _actor(message, allowlist)
        if command.action == "help":
            response = (
                "Comandos: /status DEMAND-id, /aprovacoes. "
                "Decisões são feitas somente na UI autenticada. Texto comum cria demanda. "
                f"Acesse: {approval_url}"
            )
        elif command.action in {"approvals", "approve", "reject"}:
            response = (
                "Aprovações exigem a interface autenticada da Factory. "
                f"Acesse: {approval_url}"
            )
        elif command.action == "status" and command.reference:
            kind, _, entity_id = command.reference.partition("-")
            model = Demand if kind.casefold() == "demand" else Task
            entity = session.get(model, entity_id)
            response = (
                f"{command.reference}: {entity.status}, versão "
                f"{getattr(entity, 'version', getattr(entity, 'state_version', ''))}."
                if entity is not None
                else "Demanda ou tarefa não encontrada."
            )
        else:
            response = "Comando ainda não disponível; use /ajuda ou a interface autenticada."
        _reply(session, message, response)
        return {"status": "handled", "action": command.action}

    return handle
