"""``/edit_expense`` command — show a picker, then reuse the edit menu.

The picker callback (``editexp:<expense_id>``) is handled in
:mod:`app.commands.callbacks` and opens the existing edit menu, so all
edit flows stay routed through the same handlers.
"""
from __future__ import annotations

from ..repositories import expense_repository
from ..services import trip_service
from ..telegram import keyboards, messages
from ..utils.money import fmt
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    expenses = await expense_repository.list_active(ctx.chat_id, trip.trip_id)
    if not expenses:
        await ctx.client.send_message(ctx.chat_id, messages.NO_EXPENSES)
        return

    items = [
        (f"{e.expense_name} - {fmt(e.amount)}", e.expense_id) for e in expenses
    ]
    await ctx.client.send_message(
        ctx.chat_id,
        messages.PICK_EXPENSE_TO_EDIT,
        reply_markup=keyboards.edit_expense_pick_keyboard(items),
    )
