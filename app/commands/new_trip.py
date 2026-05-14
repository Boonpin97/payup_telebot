"""``/new_trip`` flow.

Step 1 (command):       prompt for trip name.
Step 2 (text reply):    capture name, prompt for members.
Step 3 (text reply):    capture members, create trip + set active, send summary.
"""
from __future__ import annotations

from ..services import trip_service
from ..telegram import messages
from ..utils.parser import parse_usernames
from .context import CommandContext
from . import sessions

STEP_ASK_NAME = "ask_name"
STEP_ASK_MEMBERS = "ask_members"


async def handle(ctx: CommandContext) -> None:
    await sessions.start_input(
        chat_id=ctx.chat_id,
        command_name="new_trip",
        step=STEP_ASK_NAME,
        user_id=ctx.user_id,
    )
    await ctx.client.send_message(ctx.chat_id, messages.ASK_TRIP_NAME)


async def handle_input(ctx: CommandContext, session) -> None:
    text = ctx.raw_text.strip()
    if not text:
        await ctx.client.send_message(ctx.chat_id, messages.ASK_TRIP_NAME)
        return

    if session.step == STEP_ASK_NAME:
        await sessions.start_input(
            chat_id=ctx.chat_id,
            command_name="new_trip",
            step=STEP_ASK_MEMBERS,
            payload={"trip_name": text},
            user_id=ctx.user_id,
        )
        await ctx.client.send_message(
            ctx.chat_id, messages.ASK_TRIP_MEMBERS, parse_mode="Markdown"
        )
        return

    if session.step == STEP_ASK_MEMBERS:
        usernames = parse_usernames(text)
        trip_name = session.payload.get("trip_name", "Untitled trip")
        await sessions.end_input(ctx.chat_id)
        trip = await trip_service.create_trip(
            chat_id=ctx.chat_id,
            chat_title=ctx.chat_title,
            trip_name=trip_name,
            member_usernames=usernames,
            created_by_user_id=ctx.user_id,
            created_by_username=ctx.username,
        )
        await ctx.client.send_message(
            ctx.chat_id, messages.trip_created(trip.trip_name, usernames)
        )
        return
