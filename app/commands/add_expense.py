"""``/add_expense`` command."""
from __future__ import annotations

from ..services import expense_service, member_service, trip_service
from ..services.expense_service import ExpenseError
from ..telegram import keyboards, messages
from ..utils.parser import parse_add_expense
from .context import CommandContext


async def handle(ctx: CommandContext) -> None:
    if not ctx.username:
        await ctx.client.send_message(
            ctx.chat_id,
            "I can only record an expense if you have a Telegram username set.",
        )
        return

    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    try:
        parsed = parse_add_expense(ctx.args_text)
    except ValueError:
        await ctx.client.send_message(ctx.chat_id, messages.ADD_EXPENSE_USAGE)
        return

    # Make sure the payer is in the trip — auto-add the sender if missing,
    # since it's surprising for someone running /add_expense to be excluded.
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
        # The bare username is the offending value (see expense_service).
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
