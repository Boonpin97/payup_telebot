"""``/trips`` command — list non-deleted trips, marking the active one."""
from __future__ import annotations

from ..repositories import group_repository
from ..services import trip_service
from ..telegram import messages
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    trips = await trip_service.list_trips(ctx.chat_id)
    if not trips:
        await ctx.client.send_message(ctx.chat_id, messages.EMPTY_TRIP_LIST)
        return

    group = await group_repository.get(ctx.chat_id)
    active_id = group.active_trip_id if group else None
    items = [(t.trip_name, t.trip_id == active_id) for t in trips]
    await ctx.client.send_message(ctx.chat_id, messages.trips_list(items))
