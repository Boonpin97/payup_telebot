"""``/switch_trip`` command."""
from __future__ import annotations

from ..services import trip_service
from ..telegram import keyboards, messages
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    trips = await trip_service.list_trips(ctx.chat_id)
    if not trips:
        await ctx.client.send_message(ctx.chat_id, messages.EMPTY_TRIP_LIST)
        return

    items = [(t.trip_name, t.trip_id) for t in trips]
    await ctx.client.send_message(
        ctx.chat_id,
        "Select the active trip:",
        reply_markup=keyboards.trip_pick_keyboard(
            items, action=keyboards.SWITCH_TRIP_PICK
        ),
    )
