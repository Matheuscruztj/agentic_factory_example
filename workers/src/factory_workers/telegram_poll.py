"""Telegram intake pipeline into the durable, idempotent demand store."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from integrations.telegram import (
    TelegramCommand,
    TelegramError,
    TelegramPoller,
    parse_telegram_command,
    telegram_message_to_intake,
)
from task_engine.intake import IntakeError, normalize_intake, reconcile_intake
from task_engine.models import EventInbox

from factory_workers.telegram_offset import TelegramOffsetStore
from factory_workers.telegram_outbox import enqueue_telegram_message


def poll_telegram_into_database(
    poller: TelegramPoller,
    *,
    session_factory: Callable[[], Any],
    offset_store: TelegramOffsetStore,
    timeout: int = 25,
    command_handler: Callable[[Any, dict, TelegramCommand], dict | None] | None = None,
) -> dict[str, int | str]:
    """Process authorized messages and persist the offset only after success."""
    imported = 0

    def import_message(message: dict) -> None:
        nonlocal imported
        raw_text = message.get("text") or message.get("caption")
        command = None
        outcome = None
        if message.get("_edited"):
            outcome = {"status": "ignored", "reason": "EDITED_MESSAGE_UNSUPPORTED"}
        elif isinstance(raw_text, str) and raw_text.strip():
            try:
                command = parse_telegram_command(raw_text)
            except TelegramError:
                outcome = {"status": "rejected", "reason": "COMMAND_INVALID"}
        elif not message.get("_edited"):
            outcome = {"status": "ignored", "reason": "TEXT_REQUIRED"}
        if command is None or command.action != "demand":
            if outcome is None:
                outcome = {
                    "status": "ignored",
                    "reason": "TEXT_REQUIRED" if command is None else "COMMAND_HANDLER_UNAVAILABLE",
                }
            with session_factory() as session:
                try:
                    chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
                    message_id = message.get("message_id")
                    chat_id = chat.get("id")
                    if type(chat_id) is not int or type(message_id) is not int:
                        raise ValueError("TELEGRAM_MESSAGE_ID_INVALID")
                    update_id = message.get("_update_id")
                    if type(update_id) is not int:
                        raise ValueError("TELEGRAM_UPDATE_ID_INVALID")
                    event_id = f"telegram-update:{update_id}"
                    existing = session.get(EventInbox, event_id)
                    if existing is not None:
                        imported += 1
                        return
                    if command is not None and command_handler is not None:
                        outcome = command_handler(session, message, command) or {
                            "status": "handled"
                        }
                    session.merge(EventInbox(event_id=event_id, result=outcome))
                    session.commit()
                except Exception:
                    session.rollback()
                    raise
            imported += 1
            return
        if command is None:
            command = TelegramCommand(1, "demand", text=raw_text.strip())
        try:
            intake = normalize_intake(telegram_message_to_intake(message))
        except (TelegramError, IntakeError) as exc:
            raise ValueError("TELEGRAM_MESSAGE_INVALID") from exc
        with session_factory() as session:
            try:
                update_id = message.get("_update_id")
                if type(update_id) is not int:
                    raise ValueError("TELEGRAM_UPDATE_ID_INVALID")
                event_id = f"telegram-update:{update_id}"
                if session.get(EventInbox, event_id) is not None:
                    imported += 1
                    return
                demand, created = reconcile_intake(session, intake)
                chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
                chat_id = chat.get("id")
                message_id = message.get("message_id")
                if type(chat_id) is not int or type(message_id) is not int:
                    raise ValueError("TELEGRAM_MESSAGE_ID_INVALID")
                session.add(
                    EventInbox(
                        event_id=event_id,
                        result={
                            "status": "imported",
                            "demand_id": demand.id,
                            "created": created,
                        },
                    )
                )
                enqueue_telegram_message(
                    session,
                    event_id=f"telegram-demand-ack:{demand.id}",
                    chat_id=chat_id,
                    reply_to_message_id=message_id,
                    text=f"Demanda recebida e registrada. Referência: DEMAND-{demand.id}",
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
        imported += 1

    previous = offset_store.load()
    next_offset = poller.poll_once(
        offset=previous,
        process=import_message,
        timeout=timeout,
        persist_offset=offset_store.save,
    )
    return {"status": "pass", "imported": imported, "offset": next_offset}
