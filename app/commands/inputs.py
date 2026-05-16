"""Routes free-text replies to the right multi-step handler.

When the bot has prompted for input (trip name, expense name, custom split
amounts, etc.) a chat-scoped session is stored.  When a non-command text
message arrives we look up that session and dispatch by ``step``.
"""
from __future__ import annotations

from decimal import Decimal

from ..repositories import expense_repository, member_repository
from ..services import expense_service, trip_service
from ..services.expense_service import ExpenseError
from ..telegram import keyboards, messages
from ..utils.money import parse_money, sum_money
from ..utils.parser import (
    parse_amount_split,
    parse_percentage_split,
    parse_usernames,
)
from . import add_expense, members, new_trip, sessions
from .callbacks import SRC_DIRECT, SRC_EDIT
from .context import CommandContext


async def maybe_handle(ctx: CommandContext) -> bool:
    """Return ``True`` if the text was consumed by a pending session."""
    session, expired = await sessions.get_alive_input(ctx.chat_id, ctx.user_id)
    if session is None:
        if expired:
            await ctx.client.send_message(ctx.chat_id, messages.SESSION_EXPIRED)
        return False

    step = session.step
    if step in (new_trip.STEP_ASK_NAME, new_trip.STEP_ASK_MEMBERS):
        await new_trip.handle_input(ctx, session)
        return True

    if step in (members.STEP_ASK_ADD_USERNAMES, members.STEP_ASK_DELETE_USERNAMES):
        await members.handle_input(ctx, session)
        return True

    if step == add_expense.STEP_ASK_EXPENSE:
        await add_expense.handle_input(ctx, session)
        return True

    expense_id = session.payload.get("expense_id", "")
    if not expense_id:
        await sessions.end_input(ctx.chat_id, ctx.user_id)
        return True

    handlers = {
        "edit_name": _handle_edit_name,
        "edit_amount": _handle_edit_amount,
        "edit_people": _handle_edit_people,
        "split_amount": _handle_split_amount,
        "split_percent": _handle_split_percent,
    }
    handler = handlers.get(step)
    if handler is None:
        await sessions.end_input(ctx.chat_id, ctx.user_id)
        return True

    await handler(ctx, session, expense_id, session.payload.get("source", SRC_EDIT))
    return True


async def _get_expense(ctx: CommandContext, expense_id: str):
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, messages.NO_ACTIVE_TRIP)
        await sessions.end_input(ctx.chat_id, ctx.user_id)
        return None, None
    expense = await expense_repository.get(ctx.chat_id, trip.trip_id, expense_id)
    if expense is None or expense.is_deleted:
        await ctx.client.send_message(ctx.chat_id, "Expense no longer exists.")
        await sessions.end_input(ctx.chat_id, ctx.user_id)
        return None, None
    return trip, expense


async def _edit_session_message(
    ctx: CommandContext,
    session,
    *,
    text: str,
    reply_markup: dict | None = None,
    parse_mode: str | None = None,
) -> None:
    if session.callback_message_id is not None:
        await ctx.client.edit_message_text(
            ctx.chat_id,
            session.callback_message_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return
    await ctx.client.send_message(
        ctx.chat_id,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


async def _post_edit_followup(ctx: CommandContext, session, expense_id: str, source: str) -> None:
    """After a successful edit step, update the wizard message appropriately."""
    if source == SRC_EDIT:
        await _edit_session_message(
            ctx,
            session,
            text=f"{messages.EXPENSE_UPDATED}\n\n{messages.EDIT_MENU_PROMPT}",
            reply_markup=keyboards.edit_menu(expense_id),
        )
        return
    if source == SRC_DIRECT:
        await _edit_session_message(ctx, session, text=messages.EXPENSE_UPDATED)


async def _handle_edit_name(ctx: CommandContext, session, expense_id: str, source: str) -> None:
    new_name = ctx.raw_text.strip()
    if not new_name:
        await _edit_session_message(ctx, session, text=messages.EDIT_ASK_NAME)
        return
    trip, expense = await _get_expense(ctx, expense_id)
    if not expense:
        return
    expense.expense_name = new_name
    splits = await expense_repository.list_splits(ctx.chat_id, trip.trip_id, expense_id)
    await expense_repository.replace_splits(ctx.chat_id, trip.trip_id, expense, splits)
    await sessions.end_input(ctx.chat_id, ctx.user_id)
    await _post_edit_followup(ctx, session, expense_id, source)


async def _handle_edit_amount(ctx: CommandContext, session, expense_id: str, source: str) -> None:
    try:
        new_amount = parse_money(ctx.raw_text)
    except ValueError:
        await _edit_session_message(ctx, session, text=messages.INVALID_AMOUNT)
        return
    trip, expense = await _get_expense(ctx, expense_id)
    if not expense:
        return
    expense.amount = new_amount
    # Recalculate as equal split when the amount changes.
    await expense_service.replace_split_equal(ctx.chat_id, trip.trip_id, expense)
    await sessions.end_input(ctx.chat_id, ctx.user_id)
    await _post_edit_followup(ctx, session, expense_id, source)


async def _handle_edit_people(ctx: CommandContext, session, expense_id: str, source: str) -> None:
    usernames = parse_usernames(ctx.raw_text)
    if not usernames:
        await _edit_session_message(
            ctx, session, text=messages.EDIT_ASK_PEOPLE, parse_mode="Markdown"
        )
        return
    trip, expense = await _get_expense(ctx, expense_id)
    if not expense:
        return
    active = {m.username for m in await member_repository.list_active(ctx.chat_id, trip.trip_id)}
    for u in usernames:
        if u not in active:
            await ctx.client.send_message(ctx.chat_id, messages.unknown_member(u))
            return
    expense.participant_usernames = usernames
    await expense_service.replace_split_equal(ctx.chat_id, trip.trip_id, expense)
    await sessions.end_input(ctx.chat_id, ctx.user_id)
    await _post_edit_followup(ctx, session, expense_id, source)


async def _handle_split_amount(ctx: CommandContext, session, expense_id: str, source: str) -> None:
    try:
        pairs = parse_amount_split(ctx.raw_text)
    except ValueError:
        await _edit_session_message(
            ctx, session, text=messages.PARTIAL_AMOUNT_PROMPT, parse_mode="Markdown"
        )
        return
    trip, expense = await _get_expense(ctx, expense_id)
    if not expense:
        return
    user_amounts = [(p.username, p.amount) for p in pairs]
    try:
        await expense_service.replace_split_amounts(
            ctx.chat_id, trip.trip_id, expense, user_amounts
        )
    except ExpenseError as exc:
        if str(exc) == "amount_mismatch":
            actual = sum_money(a for _, a in user_amounts)
            await _edit_session_message(
                ctx,
                session,
                text=messages.amount_split_mismatch(actual, expense.amount),
            )
            return
        await _edit_session_message(ctx, session, text=str(exc))
        return
    await sessions.end_input(ctx.chat_id, ctx.user_id)
    await _post_edit_followup(ctx, session, expense_id, source)


async def _handle_split_percent(ctx: CommandContext, session, expense_id: str, source: str) -> None:
    try:
        pairs = parse_percentage_split(ctx.raw_text)
    except ValueError:
        await _edit_session_message(
            ctx, session, text=messages.PARTIAL_PERCENT_PROMPT, parse_mode="Markdown"
        )
        return
    trip, expense = await _get_expense(ctx, expense_id)
    if not expense:
        return
    user_percents = [(p.username, p.percent) for p in pairs]
    try:
        await expense_service.replace_split_percentages(
            ctx.chat_id, trip.trip_id, expense, user_percents
        )
    except ExpenseError as exc:
        if str(exc) == "percent_mismatch":
            total = sum((p.percent for p in pairs), Decimal(0))
            await _edit_session_message(
                ctx,
                session,
                text=messages.percentage_split_mismatch(total),
            )
            return
        await _edit_session_message(ctx, session, text=str(exc))
        return
    await sessions.end_input(ctx.chat_id, ctx.user_id)
    await _post_edit_followup(ctx, session, expense_id, source)
