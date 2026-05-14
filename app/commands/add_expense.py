"""``/add_expense`` command.

Two entry paths:
  1. Inline args: ``/add_expense pasta 10 [@user ...]`` — parsed directly.
  2. Tapped from the slash menu (no args possible): bot prompts for the
     expense details and reads the reply in :func:`handle_input`.
"""
from __future__ import annotations

from ..services import expense_service, member_service, trip_service
from ..services.expense_service import ExpenseError
from ..telegram import keyboards, messages
from ..utils.parser import parse_add_expense
from . import sessions
from .context import CommandContext

STEP_ASK_EXPENSE = "ask_expense"

_NO_USERNAME_MSG = (
    "I can only record an expense if you have a Telegram username set."
)


async def handle(ctx: CommandContext) -> None:
    if not ctx.username:
        await ctx.client.send_message(ctx.chat_id, _NO_USERNAME_MSG)
        return

    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    if not ctx.args_text or not ctx.args_text.strip():
        await sessions.start_input(
            chat_id=ctx.chat_id,
            command_name="add_expense",
            step=STEP_ASK_EXPENSE,
            user_id=ctx.user_id,
        )
        await ctx.client.send_message(
            ctx.chat_id, messages.ASK_EXPENSE, parse_mode="Markdown"
        )
        return

    await _create_from_args(ctx, trip, ctx.args_text)


async def handle_input(ctx: CommandContext, session) -> None:
    if not ctx.username:
        await sessions.end_input(ctx.chat_id)
        await ctx.client.send_message(ctx.chat_id, _NO_USERNAME_MSG)
        return

    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await sessions.end_input(ctx.chat_id)
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    text = ctx.raw_text.strip()
    if not text:
        await ctx.client.send_message(
            ctx.chat_id, messages.ASK_EXPENSE, parse_mode="Markdown"
        )
        return

    await sessions.end_input(ctx.chat_id)
    await _create_from_args(ctx, trip, text)


async def _create_from_args(ctx: CommandContext, trip, args_text: str) -> None:
    try:
        parsed = parse_add_expense(args_text)
    except ValueError:
        await ctx.client.send_message(ctx.chat_id, messages.ADD_EXPENSE_USAGE)
        return

    active = set(await member_service.active_usernames(ctx.chat_id, trip.trip_id))
    if ctx.username not in active:
        await member_service.add_members(ctx.chat_id, trip.trip_id, [ctx.username])

    try:
        created = await expense_service.add_expense(
            chat_id=ctx.chat_id,
            trip_id=trip.trip_id,
            group_id=trip.group_id,
            name=parsed.name,
            amount=parsed.amount,
            paid_by_user_id=ctx.user_id,
            paid_by_username=ctx.username,
            participants=list(parsed.participants),
        )
    except ExpenseError as exc:
        await ctx.client.send_message(ctx.chat_id, messages.unknown_member(str(exc)))
        return

    expense = created.expense
    if not parsed.participants:
        text = messages.expense_added_all_members(
            expense.expense_name, expense.amount, expense.paid_by_username
        )
    else:
        per_person = created.splits[0].amount_owed if created.splits else expense.amount
        text = messages.expense_added_with_participants(
            expense.expense_name,
            expense.amount,
            expense.paid_by_username,
            expense.participant_usernames,
            per_person,
        )

    await ctx.client.send_message(
        ctx.chat_id,
        text,
        reply_markup=keyboards.expense_actions(expense.expense_id),
    )
