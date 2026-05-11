"""``/summary`` command."""
from __future__ import annotations

from ..services import expense_service, trip_service
from ..telegram import messages
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    summary = await expense_service.compute_summary(ctx.chat_id, trip.trip_id)
    text = messages.trip_summary(
        trip.trip_name,
        summary.members,
        summary.total_spent,
        summary.paid_by,
        summary.net_balance,
        summary.settlements,
    )
    await ctx.client.send_message(ctx.chat_id, text)
