"""``/add_members`` and ``/delete_members`` commands."""
from __future__ import annotations

from ..services import member_service, trip_service
from ..telegram import messages
from ..utils.parser import parse_usernames
from .context import CommandContext


async def add(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    usernames = parse_usernames(ctx.args_text)
    if not usernames:
        await ctx.client.send_message(
            ctx.chat_id,
            "Please provide one or more usernames, e.g.\n/add_members @alice @bob",
        )
        return

    result = await member_service.add_members(ctx.chat_id, trip.trip_id, usernames)
    text = messages.members_added(
        added=result.added,
        already_present=result.already_present,
        current_members=result.current_members,
        trip_name=trip.trip_name,
    )
    await ctx.client.send_message(ctx.chat_id, text)


async def delete(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    usernames = parse_usernames(ctx.args_text)
    if not usernames:
        await ctx.client.send_message(
            ctx.chat_id,
            "Please provide one or more usernames, e.g.\n/delete_members @alice",
        )
        return

    result = await member_service.remove_members(ctx.chat_id, trip.trip_id, usernames)
    text = messages.members_removed(
        removed=result.removed,
        not_in_trip=result.not_in_trip,
        current_members=result.current_members,
        trip_name=trip.trip_name,
    )
    await ctx.client.send_message(ctx.chat_id, text)
