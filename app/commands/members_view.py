"""``/members`` command — show active members of the active trip."""
from __future__ import annotations

from ..services import member_service, trip_service
from ..telegram import messages
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    usernames = await member_service.active_usernames(ctx.chat_id, trip.trip_id)
    await ctx.client.send_message(
        ctx.chat_id, messages.members_list(trip.trip_name, usernames)
    )
