"""Telegram update dispatcher.

Routes ``message`` updates (commands and free text) and ``callback_query``
updates (inline button clicks) to handlers in :mod:`app.commands`.
"""
from __future__ import annotations

from typing import Optional

from ..commands import (
    add_expense,
    callbacks,
    cancel,
    delete_payment,
    delete_trip,
    edit_expense,
    expenses_view,
    inputs,
    list_expenses,
    members,
    members_view,
    new_trip,
    settle,
    summary,
    switch_trip,
    trips_view,
)
from ..commands.context import CallbackContext, CommandContext
from ..utils.logging import get_logger
from .bot import get_telegram_client
from .messages import GREETING

logger = get_logger(__name__)


async def handle_update(update: dict) -> None:
    if "callback_query" in update:
        await _handle_callback_query(update["callback_query"])
        return

    if "message" in update:
        await _handle_message(update["message"])
        return

    if "my_chat_member" in update:
        await _handle_my_chat_member(update["my_chat_member"])
        return

    # Other update types (edited_message, poll, etc.) are ignored.
    logger.debug("ignored update %s", update.get("update_id"))


# --- message routing ----------------------------------------------------


async def _handle_message(msg: dict) -> None:
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return

    if msg.get("new_chat_members"):
        # A user (possibly the bot itself) joined. Greeting is sent more
        # reliably via the my_chat_member update; nothing else to do here.
        return

    sender = msg.get("from") or {}
    username = (sender.get("username") or "").lower()
    user_id = sender.get("id")
    text = msg.get("text", "") or msg.get("caption", "")

    ctx = CommandContext(
        chat_id=chat_id,
        chat_title=chat.get("title"),
        user_id=user_id,
        username=username,
        message_id=msg.get("message_id"),
        raw_text=text,
        args_text="",
        client=get_telegram_client(),
    )

    if text.startswith("/"):
        await _route_command(ctx, text)
        return

    # Non-command text: maybe an answer to an in-progress prompt.
    await inputs.maybe_handle(ctx)


async def _start_handler(ctx: CommandContext) -> None:
    await ctx.client.send_message(ctx.chat_id, GREETING)


COMMAND_HANDLERS = {
    "new_trip": new_trip.handle,
    "add_expense": add_expense.handle,
    "edit_expense": edit_expense.handle,
    "expenses": expenses_view.handle,
    "summary": summary.handle,
    "list_expenses": list_expenses.handle,
    "settle": settle.handle,
    "delete_payment": delete_payment.handle,
    "members": members_view.handle,
    "add_members": members.add,
    "delete_members": members.delete,
    "trips": trips_view.handle,
    "switch_trip": switch_trip.handle,
    "delete_trip": delete_trip.handle,
    "cancel": cancel.handle,
    "start": _start_handler,
    "help": _start_handler,
}


async def _route_command(ctx: CommandContext, text: str) -> None:
    name, args = _parse_command(text)
    handler = COMMAND_HANDLERS.get(name)
    if handler is None:
        return
    ctx.args_text = args
    await handler(ctx)


def _parse_command(text: str) -> tuple[str, str]:
    """Strip the leading ``/``, drop optional ``@botname`` suffix."""
    body = text[1:] if text.startswith("/") else text
    head, _, args = body.partition(" ")
    if "@" in head:
        head = head.split("@", 1)[0]
    return head, args


# --- callback query routing --------------------------------------------


async def _handle_callback_query(cq: dict) -> None:
    message = cq.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return

    sender = cq.get("from") or {}
    ctx = CallbackContext(
        chat_id=chat_id,
        user_id=sender.get("id"),
        username=(sender.get("username") or "").lower(),
        message_id=message_id,
        callback_query_id=cq.get("id", ""),
        data=cq.get("data", ""),
        client=get_telegram_client(),
    )
    message_date_unix = int(message.get("date") or 0)
    await callbacks.handle(ctx, message_date_unix)


# --- bot membership change ---------------------------------------------


async def _handle_my_chat_member(update: dict) -> None:
    chat = update.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    new_status = (update.get("new_chat_member") or {}).get("status")
    old_status = (update.get("old_chat_member") or {}).get("status")
    # Greet only when the bot transitions from "not present" to "present".
    if new_status in {"member", "administrator"} and old_status in {"left", "kicked", None}:
        client = get_telegram_client()
        try:
            await client.send_message(chat_id, GREETING)
        except Exception:  # noqa: BLE001
            logger.exception("failed to send greeting to chat %s", chat_id)
