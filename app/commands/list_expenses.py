"""``/list_expenses`` command — shows all expenses in the active trip."""
from __future__ import annotations

from ..repositories import expense_repository
from ..services import trip_service
from ..telegram import messages
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    expenses = await expense_repository.list_active(ctx.chat_id, trip.trip_id)
    text = messages.expense_list(trip.trip_name, expenses)
    await ctx.client.send_message(ctx.chat_id, text)
