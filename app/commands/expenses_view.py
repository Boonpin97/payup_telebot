"""``/expenses`` command — newest 10 active expenses for the active trip."""
from __future__ import annotations

from ..repositories import expense_repository
from ..services import trip_service
from ..telegram import messages
from .context import CommandContext

LIMIT = 10


async def handle(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    expenses = await expense_repository.list_active(ctx.chat_id, trip.trip_id)
    if not expenses:
        await ctx.client.send_message(ctx.chat_id, messages.NO_EXPENSES)
        return

    expenses.sort(key=lambda e: e.created_at, reverse=True)
    newest = expenses[:LIMIT]
    remaining = max(len(expenses) - LIMIT, 0)
    items = [(e.expense_name, e.amount, e.paid_by_username) for e in newest]
    await ctx.client.send_message(
        ctx.chat_id, messages.expenses_list(items, remaining)
    )
