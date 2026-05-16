"""Inline-button (``callback_query``) handling for every flow."""
from __future__ import annotations

from datetime import datetime, timezone

from ..repositories import expense_repository, member_repository
from ..services import expense_service, trip_service
from ..services.expense_service import ExpenseError
from ..telegram import keyboards, messages
from ..telegram.bot import TelegramAPIError
from ..utils.money import fmt
from ..utils.timeouts import utcnow
from . import sessions
from .context import CallbackContext

# Source flag stashed on input-pending sessions for partial-split flows.
SRC_EDIT = "edit"
SRC_DIRECT = "direct"


def _is_message_expired(callback_message_date_unix: int, *, ttl: int = 180) -> bool:
    msg_dt = datetime.fromtimestamp(callback_message_date_unix, tz=timezone.utc)
    return (utcnow() - msg_dt).total_seconds() > ttl


def parse_data(data: str) -> tuple[str, str]:
    """Split ``"<action>:<id>"``. Empty ``id`` for actions with no payload."""
    if ":" not in data:
        return data, ""
    action, _, ident = data.partition(":")
    return action, ident


async def handle(ctx: CallbackContext, message_date_unix: int) -> None:
    if _is_message_expired(message_date_unix):
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=messages.SESSION_EXPIRED, show_alert=True
        )
        # Best-effort: clear stale buttons.
        try:
            await ctx.client.edit_message_reply_markup(
                ctx.chat_id, ctx.message_id, reply_markup=None
            )
        except TelegramAPIError:
            pass
        return

    action, ident = parse_data(ctx.data)

    handler_map = {
        keyboards.EXPENSE_EDIT: _on_expense_edit,
        keyboards.EXPENSE_DELETE: _on_expense_delete,
        keyboards.EXPENSE_PARTIAL: _on_expense_partial,
        keyboards.EDIT_NAME: _on_edit_name,
        keyboards.EDIT_AMOUNT: _on_edit_amount,
        keyboards.EDIT_PEOPLE: _on_edit_people,
        keyboards.EDIT_PARTIAL: _on_edit_partial,
        keyboards.EDIT_DONE: _on_edit_done,
        keyboards.SPLIT_EQUAL: _on_split_equal,
        keyboards.SPLIT_AMOUNT: _on_split_amount,
        keyboards.SPLIT_PERCENT: _on_split_percent,
        keyboards.DELETE_PAYMENT_PICK: _on_delete_payment_pick,
        keyboards.EDIT_EXPENSE_PICK: _on_edit_expense_pick,
        keyboards.SETTLE_PICK: _on_settle_pick,
        keyboards.SWITCH_TRIP_PICK: _on_switch_trip_pick,
        keyboards.DELETE_TRIP_PICK: _on_delete_trip_pick,
        keyboards.DELETE_TRIP_CONFIRM: _on_delete_trip_confirm,
        keyboards.DELETE_TRIP_CANCEL: _on_delete_trip_cancel,
    }
    handler = handler_map.get(action)
    if handler is None:
        await ctx.client.answer_callback_query(ctx.callback_query_id)
        return

    await handler(ctx, ident)


# --- expense action buttons ---------------------------------------------


async def _on_expense_edit(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(
        ctx.chat_id,
        "What would you like to edit?",
        reply_markup=keyboards.edit_menu(expense_id),
    )


async def _on_expense_delete(ctx: CallbackContext, expense_id: str) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=messages.NO_ACTIVE_TRIP, show_alert=True
        )
        return
    await expense_service.delete_expense(ctx.chat_id, trip.trip_id, expense_id)
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(ctx.chat_id, messages.EXPENSE_DELETED_SHORT)


async def _on_expense_partial(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(
        ctx.chat_id,
        "Choose a split type:",
        reply_markup=keyboards.partial_split_menu(expense_id),
    )


# --- edit menu options --------------------------------------------------


async def _start_text_input(
    ctx: CallbackContext,
    *,
    expense_id: str,
    kind: str,
    prompt: str,
    source: str = SRC_EDIT,
    parse_mode: str | None = None,
) -> None:
    await sessions.start_input(
        chat_id=ctx.chat_id,
        command_name="edit_expense",
        step=kind,
        payload={"expense_id": expense_id, "source": source},
        user_id=ctx.user_id,
        callback_message_id=ctx.message_id,
    )
    await ctx.client.send_message(ctx.chat_id, prompt, parse_mode=parse_mode)


async def _on_edit_name(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await _start_text_input(
        ctx, expense_id=expense_id, kind="edit_name", prompt=messages.EDIT_ASK_NAME
    )


async def _on_edit_amount(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await _start_text_input(
        ctx, expense_id=expense_id, kind="edit_amount", prompt=messages.EDIT_ASK_AMOUNT
    )


async def _on_edit_people(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await _start_text_input(
        ctx,
        expense_id=expense_id,
        kind="edit_people",
        prompt=messages.EDIT_ASK_PEOPLE,
        parse_mode="Markdown",
    )


async def _on_edit_partial(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(
        ctx.chat_id,
        "Choose a split type:",
        reply_markup=keyboards.partial_split_menu(expense_id),
    )


async def _on_edit_done(ctx: CallbackContext, expense_id: str) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(ctx.chat_id, messages.EXPENSE_UPDATED)
    if trip is None:
        return
    await _send_expense_summary(ctx, trip.trip_id, expense_id)


# --- partial split sub-menu ---------------------------------------------


async def _on_split_equal(ctx: CallbackContext, expense_id: str) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=messages.NO_ACTIVE_TRIP, show_alert=True
        )
        return
    expense = await expense_repository.get(ctx.chat_id, trip.trip_id, expense_id)
    if expense is None:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text="Expense no longer exists.", show_alert=True
        )
        return
    splits = await expense_service.replace_split_equal(ctx.chat_id, trip.trip_id, expense)
    per_person = splits[0].amount_owed if splits else expense.amount
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(ctx.chat_id, messages.equal_split_done(per_person))


async def _on_split_amount(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await _start_text_input(
        ctx,
        expense_id=expense_id,
        kind="split_amount",
        prompt=messages.PARTIAL_AMOUNT_PROMPT,
        source=SRC_DIRECT,
        parse_mode="Markdown",
    )


async def _on_split_percent(ctx: CallbackContext, expense_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await _start_text_input(
        ctx,
        expense_id=expense_id,
        kind="split_percent",
        prompt=messages.PARTIAL_PERCENT_PROMPT,
        source=SRC_DIRECT,
        parse_mode="Markdown",
    )


# --- /delete_payment, /switch_trip, /delete_trip pickers ---------------


async def _on_delete_payment_pick(ctx: CallbackContext, expense_id: str) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=messages.NO_ACTIVE_TRIP, show_alert=True
        )
        return
    expense = await expense_repository.get(ctx.chat_id, trip.trip_id, expense_id)
    if expense is None or expense.is_deleted:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text="Expense no longer exists.", show_alert=True
        )
        return
    await expense_service.delete_expense(ctx.chat_id, trip.trip_id, expense_id)
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(
        ctx.chat_id,
        f"Expense deleted: {expense.expense_name} - {fmt(expense.amount)}",
    )


async def _on_settle_pick(ctx: CallbackContext, index_str: str) -> None:
    try:
        idx = int(index_str)
    except ValueError:
        await ctx.client.answer_callback_query(ctx.callback_query_id)
        return

    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=messages.NO_ACTIVE_TRIP, show_alert=True
        )
        return

    # Recompute the current simplified debts so a stale button settles the
    # *current* debt at that position (or the user gets a clear "gone").
    summary = await expense_service.compute_summary(ctx.chat_id, trip.trip_id)
    if idx < 0 or idx >= len(summary.settlements):
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=messages.SETTLE_DEBT_GONE, show_alert=True
        )
        return

    debtor, creditor, amount = summary.settlements[idx]

    active_members = await member_repository.list_active(ctx.chat_id, trip.trip_id)
    debtor_user_id = next(
        (m.telegram_user_id for m in active_members if m.username == debtor), None
    )

    try:
        await expense_service.add_settlement(
            chat_id=ctx.chat_id,
            trip_id=trip.trip_id,
            group_id=trip.group_id,
            payer_user_id=debtor_user_id,
            payer_username=debtor,
            recipient_username=creditor,
            amount=amount,
        )
    except ExpenseError as exc:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=str(exc), show_alert=True
        )
        return

    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(
        ctx.chat_id, messages.settlement_recorded(debtor, creditor, amount)
    )


async def _on_edit_expense_pick(ctx: CallbackContext, expense_id: str) -> None:
    trip = await trip_service.get_active_trip(ctx.chat_id)
    if trip is None:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text=messages.NO_ACTIVE_TRIP, show_alert=True
        )
        return
    expense = await expense_repository.get(ctx.chat_id, trip.trip_id, expense_id)
    if expense is None or expense.is_deleted:
        await ctx.client.answer_callback_query(
            ctx.callback_query_id, text="Expense no longer exists.", show_alert=True
        )
        return
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(
        ctx.chat_id,
        messages.EDIT_MENU_PROMPT,
        reply_markup=keyboards.edit_menu(expense_id),
    )


async def _on_switch_trip_pick(ctx: CallbackContext, trip_id: str) -> None:
    trip = await trip_service.switch_active_trip(ctx.chat_id, trip_id)
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, "Trip no longer exists.")
        return
    from ..services import member_service

    members = await member_service.active_usernames(ctx.chat_id, trip.trip_id)
    await ctx.client.send_message(
        ctx.chat_id, messages.trip_switched(trip.trip_name, members)
    )


async def _on_delete_trip_pick(ctx: CallbackContext, trip_id: str) -> None:
    from ..repositories import trip_repository

    trip = await trip_repository.get(ctx.chat_id, trip_id)
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, "Trip no longer exists.")
        return
    await ctx.client.send_message(
        ctx.chat_id,
        messages.confirm_delete_trip_text(trip.trip_name),
        reply_markup=keyboards.confirm_delete_trip(trip_id),
    )


async def _on_delete_trip_confirm(ctx: CallbackContext, trip_id: str) -> None:
    trip = await trip_service.delete_trip(ctx.chat_id, trip_id)
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    if trip is None:
        await ctx.client.send_message(ctx.chat_id, "Trip no longer exists.")
        return
    await ctx.client.send_message(ctx.chat_id, messages.trip_deleted(trip.trip_name))


async def _on_delete_trip_cancel(ctx: CallbackContext, trip_id: str) -> None:
    await ctx.client.answer_callback_query(ctx.callback_query_id)
    await ctx.client.send_message(ctx.chat_id, "Cancelled.")


# --- helpers ------------------------------------------------------------


async def _send_expense_summary(ctx: CallbackContext, trip_id: str, expense_id: str) -> None:
    expense = await expense_repository.get(ctx.chat_id, trip_id, expense_id)
    if expense is None or expense.is_deleted:
        await ctx.client.send_message(ctx.chat_id, "Expense no longer exists.")
        return
    splits = await expense_repository.list_splits(ctx.chat_id, trip_id, expense_id)
    pairs = [(s.username, s.amount_owed) for s in splits]
    await ctx.client.send_message(
        ctx.chat_id,
        messages.expense_summary(
            expense.expense_name,
            expense.amount,
            expense.paid_by_username,
            expense.split_type,
            pairs,
        ),
    )
