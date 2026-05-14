"""``/cancel`` command.

Ends any chat-scoped input-pending session so the user can abandon a
multi-step prompt (e.g. /new_trip, /add_expense, edit/partial split
flows). Anyone in the chat may run /cancel.
"""
from __future__ import annotations

from ..telegram import messages
from . import sessions
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    session = await sessions.get_alive_input(ctx.chat_id)
    if session is None:
        await ctx.client.send_message(ctx.chat_id, messages.CANCEL_NOTHING)
        return
    await sessions.end_input(ctx.chat_id)
    await ctx.client.send_message(ctx.chat_id, messages.CANCEL_DONE)
