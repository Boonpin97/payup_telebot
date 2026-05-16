"""``/settle`` command — record that one member paid another outside the app.

Two entry paths:
  1. No args: show a button picker listing the simplified debts.
     Tapping one settles that debt for its current amount.
  2. Inline ``/settle @username amount``: settles a specific amount
     between the sender and the target (useful for partial settlements
     that don't match a simplified-debt row).
"""
from __future__ import annotations

from ..services import expense_service, member_service, trip_service
from ..services.expense_service import ExpenseError
from ..telegram import keyboards, messages
from ..utils.parser import parse_settle
from .context import CommandContext

_NO_USERNAME_MSG = (
    "I can only record a settlement if you have a Telegram username set."
)


async def handle(ctx: CommandContext) -> None:
    if not ctx.username:
        await ctx.client.send_message(ctx.chat_id, _NO_USERNAME_MSG)
        return

    if not ctx.args_text.strip():
        await _show_picker(ctx)
        return

    try:
        recipient_username, amount = parse_settle(ctx.args_text)
    except ValueError:
        await ctx.client.send_message(ctx.chat_id, messages.SETTLE_USAGE, parse_mode="Markdown")
        return

    if recipient_username == ctx.username:
        await ctx.client.send_message(ctx.chat_id, messages.SETTLE_SELF_ERROR)
        return

    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    active = set(await member_service.active_usernames(ctx.chat_id, trip.trip_id))
    if ctx.username not in active:
        await member_service.add_members(ctx.chat_id, trip.trip_id, [ctx.username])

    if recipient_username not in active:
        await ctx.client.send_message(ctx.chat_id, messages.unknown_member(recipient_username))
        return

    try:
        await expense_service.add_settlement(
            chat_id=ctx.chat_id,
            trip_id=trip.trip_id,
            group_id=trip.group_id,
            payer_user_id=ctx.user_id,
            payer_username=ctx.username,
            recipient_username=recipient_username,
            amount=amount,
        )
    except ExpenseError as exc:
        await ctx.client.send_message(ctx.chat_id, messages.unknown_member(str(exc)))
        return

    await ctx.client.send_message(
        ctx.chat_id,
        messages.settlement_recorded(ctx.username, recipient_username, amount),
    )


async def _show_picker(ctx: CommandContext) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        return

    summary = await expense_service.compute_summary(ctx.chat_id, trip.trip_id)
    if not summary.settlements:
        await ctx.client.send_message(ctx.chat_id, messages.ALL_SETTLED)
        return

    labels = [
        messages.settle_button_label(debtor, creditor, amount)
        for debtor, creditor, amount in summary.settlements
    ]
    await ctx.client.send_message(
        ctx.chat_id,
        messages.PICK_DEBT_TO_SETTLE,
        reply_markup=keyboards.settle_pick_keyboard(labels),
    )
