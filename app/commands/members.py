"""``/add_members`` and ``/delete_members`` commands.

If the command arrives with no usernames (e.g. tapped from the Telegram
slash menu, which sends the command immediately), the bot starts a session
and prompts the user for usernames in a follow-up message.
"""
from __future__ import annotations

from ..services import member_service, trip_service
from ..telegram import messages
from ..utils.parser import parse_usernames
from . import sessions
from .context import CommandContext

STEP_ASK_ADD_USERNAMES = "ask_add_usernames"
STEP_ASK_DELETE_USERNAMES = "ask_delete_usernames"

ASK_ADD_USERNAMES = (
    "Who would you like to add to this trip?\n\n"
    "E.g.\n`@alice` `@bob`"
)
ASK_DELETE_USERNAMES = (
    "Who would you like to remove from this trip?\n\n"
    "E.g.\n`@alice`"
)


async def add(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    usernames = parse_usernames(ctx.args_text)
    if not usernames:
        await sessions.start_input(
            chat_id=ctx.chat_id,
            command_name="add_members",
            step=STEP_ASK_ADD_USERNAMES,
            user_id=ctx.user_id,
        )
        await ctx.client.send_message(
            ctx.chat_id, ASK_ADD_USERNAMES, parse_mode="Markdown"
        )
        return

    await _apply_add(ctx, trip, usernames)


async def delete(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    usernames = parse_usernames(ctx.args_text)
    if not usernames:
        await sessions.start_input(
            chat_id=ctx.chat_id,
            command_name="delete_members",
            step=STEP_ASK_DELETE_USERNAMES,
            user_id=ctx.user_id,
        )
        await ctx.client.send_message(
            ctx.chat_id, ASK_DELETE_USERNAMES, parse_mode="Markdown"
        )
        return

    await _apply_delete(ctx, trip, usernames)


async def handle_input(ctx: CommandContext, session) -> None:
    usernames = parse_usernames(ctx.raw_text)
    if not usernames:
        prompt = (
            ASK_ADD_USERNAMES
            if session.step == STEP_ASK_ADD_USERNAMES
            else ASK_DELETE_USERNAMES
        )
        await ctx.client.send_message(ctx.chat_id, prompt, parse_mode="Markdown")
        return

    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await sessions.end_input(ctx.chat_id)
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    await sessions.end_input(ctx.chat_id)
    if session.step == STEP_ASK_ADD_USERNAMES:
        await _apply_add(ctx, trip, usernames)
    else:
        await _apply_delete(ctx, trip, usernames)


async def _apply_add(ctx: CommandContext, trip, usernames: list[str]) -> None:
    result = await member_service.add_members(ctx.chat_id, trip.trip_id, usernames)
    text = messages.members_added(
        added=result.added,
        already_present=result.already_present,
        current_members=result.current_members,
        trip_name=trip.trip_name,
    )
    await ctx.client.send_message(ctx.chat_id, text)


async def _apply_delete(ctx: CommandContext, trip, usernames: list[str]) -> None:
    result = await member_service.remove_members(ctx.chat_id, trip.trip_id, usernames)
    text = messages.members_removed(
        removed=result.removed,
        not_in_trip=result.not_in_trip,
        current_members=result.current_members,
        trip_name=trip.trip_name,
    )
    await ctx.client.send_message(ctx.chat_id, text)
