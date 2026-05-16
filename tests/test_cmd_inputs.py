"""Tests for inputs.maybe_handle: session routing, expiry, and user scoping."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.commands import add_expense, inputs, members, new_trip
from app.commands.add_expense import STEP_ASK_EXPENSE
from app.commands.members import STEP_ASK_ADD_USERNAMES, STEP_ASK_DELETE_USERNAMES
from app.commands.new_trip import STEP_ASK_MEMBERS, STEP_ASK_NAME
from app.telegram import messages

from .conftest import (
    CHAT_ID,
    EXPENSE_ID,
    TRIP_ID,
    USER_A_ID,
    USER_B_ID,
    USER_B_NAME,
    make_ctx,
    make_session,
)


def _alive(session):
    """Return (session, not_expired) as get_if_alive would."""
    return (session, False)


def _expired():
    return (None, True)


def _no_session():
    return (None, False)


def _patch_get_if_alive(return_value):
    return patch(
        "app.services.session_service.get_if_alive",
        new_callable=AsyncMock,
        return_value=return_value,
    )


def _patch_end():
    return patch("app.services.session_service.end", new_callable=AsyncMock)


# ---------------------------------------------------------------------------
# No session / expiry
# ---------------------------------------------------------------------------


async def test_no_session_returns_false_and_sends_nothing():
    ctx = make_ctx(raw_text="hello")
    with _patch_get_if_alive(_no_session()):
        result = await inputs.maybe_handle(ctx)
    assert result is False
    ctx.client.send_message.assert_not_called()


async def test_expired_session_sends_session_expired_message():
    ctx = make_ctx(raw_text="BKK", user_id=USER_A_ID)
    with _patch_get_if_alive(_expired()), _patch_end():
        result = await inputs.maybe_handle(ctx)
    assert result is False
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.SESSION_EXPIRED)


async def test_expired_session_returns_false():
    ctx = make_ctx(raw_text="anything")
    with _patch_get_if_alive(_expired()), _patch_end():
        result = await inputs.maybe_handle(ctx)
    assert result is False


# ---------------------------------------------------------------------------
# User scoping: only session owner's reply is consumed
# ---------------------------------------------------------------------------


async def test_user_b_text_ignored_when_only_user_a_has_session():
    """User B sends text while User A's session is active — must be ignored."""
    ctx_b = make_ctx(raw_text="BKK", user_id=USER_B_ID, username=USER_B_NAME)

    # For User B's session key → no session exists
    with _patch_get_if_alive(_no_session()):
        result = await inputs.maybe_handle(ctx_b)

    assert result is False
    ctx_b.client.send_message.assert_not_called()


async def test_user_a_text_consumed_when_user_a_has_session():
    ctx_a = make_ctx(raw_text="BKK", user_id=USER_A_ID)
    session = make_session("new_trip", STEP_ASK_NAME)

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.new_trip.handle_input", new_callable=AsyncMock) as mock_handler:
        result = await inputs.maybe_handle(ctx_a)

    assert result is True
    mock_handler.assert_called_once()


# ---------------------------------------------------------------------------
# Dispatch to correct handler by step
# ---------------------------------------------------------------------------


async def test_dispatches_ask_name_to_new_trip():
    ctx = make_ctx(raw_text="Trip Name")
    session = make_session("new_trip", STEP_ASK_NAME)

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.new_trip.handle_input", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once_with(ctx, session)


async def test_dispatches_ask_members_to_new_trip():
    ctx = make_ctx(raw_text="@bob")
    session = make_session("new_trip", STEP_ASK_MEMBERS)

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.new_trip.handle_input", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once_with(ctx, session)


async def test_dispatches_ask_expense_to_add_expense():
    ctx = make_ctx(raw_text="pasta 10")
    session = make_session("add_expense", STEP_ASK_EXPENSE)

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.add_expense.handle_input", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once_with(ctx, session)


async def test_dispatches_ask_add_usernames_to_members():
    ctx = make_ctx(raw_text="@charlie")
    session = make_session("add_members", STEP_ASK_ADD_USERNAMES)

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.members.handle_input", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once_with(ctx, session)


async def test_dispatches_ask_delete_usernames_to_members():
    ctx = make_ctx(raw_text="@charlie")
    session = make_session("delete_members", STEP_ASK_DELETE_USERNAMES)

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.members.handle_input", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once_with(ctx, session)


# ---------------------------------------------------------------------------
# Edit/split steps (require expense_id in payload)
# ---------------------------------------------------------------------------


async def test_unknown_step_no_expense_id_ends_session_silently():
    ctx = make_ctx(raw_text="whatever")
    session = make_session("edit_expense", "unknown_step", payload={})

    with _patch_get_if_alive(_alive(session)), _patch_end() as mock_end:
        result = await inputs.maybe_handle(ctx)

    assert result is True
    mock_end.assert_called_once()
    ctx.client.send_message.assert_not_called()


async def test_unknown_step_with_expense_id_ends_session_silently():
    ctx = make_ctx(raw_text="whatever")
    session = make_session("edit_expense", "totally_unknown", payload={"expense_id": EXPENSE_ID})

    with _patch_get_if_alive(_alive(session)), _patch_end() as mock_end:
        result = await inputs.maybe_handle(ctx)

    assert result is True
    mock_end.assert_called_once()


async def test_edit_name_step_dispatches_correctly():
    ctx = make_ctx(raw_text="New Name")
    session = make_session("edit_expense", "edit_name", payload={"expense_id": EXPENSE_ID})

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.inputs._handle_edit_name", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once()


async def test_edit_amount_step_dispatches_correctly():
    ctx = make_ctx(raw_text="25.00")
    session = make_session("edit_expense", "edit_amount", payload={"expense_id": EXPENSE_ID})

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.inputs._handle_edit_amount", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once()


async def test_edit_people_step_dispatches_correctly():
    ctx = make_ctx(raw_text="@alice @bob")
    session = make_session("edit_expense", "edit_people", payload={"expense_id": EXPENSE_ID})

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.inputs._handle_edit_people", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once()


async def test_split_amount_step_dispatches_correctly():
    ctx = make_ctx(raw_text="@alice 10 @bob 5")
    session = make_session("edit_expense", "split_amount", payload={"expense_id": EXPENSE_ID})

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.inputs._handle_split_amount", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once()


async def test_split_percent_step_dispatches_correctly():
    ctx = make_ctx(raw_text="@alice 60 @bob 40")
    session = make_session("edit_expense", "split_percent", payload={"expense_id": EXPENSE_ID})

    with _patch_get_if_alive(_alive(session)), \
         patch("app.commands.inputs._handle_split_percent", new_callable=AsyncMock) as mock_h:
        await inputs.maybe_handle(ctx)

    mock_h.assert_called_once()


async def test_edit_amount_invalid_input_edits_existing_prompt():
    ctx = make_ctx(raw_text="not-a-number")
    session = make_session("edit_expense", "edit_amount", payload={"expense_id": EXPENSE_ID})
    session.callback_message_id = 77

    await inputs._handle_edit_amount(ctx, session, EXPENSE_ID, "edit")

    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        77,
        messages.INVALID_AMOUNT,
        reply_markup=None,
        parse_mode=None,
    )
    ctx.client.send_message.assert_not_called()


async def test_edit_name_success_reuses_existing_wizard_message():
    ctx = make_ctx(raw_text="Dinner")
    session = make_session("edit_expense", "edit_name", payload={"expense_id": EXPENSE_ID})
    session.callback_message_id = 77

    expense = type("Expense", (), {"expense_name": "Old", "is_deleted": False})()
    trip = type("Trip", (), {"trip_id": TRIP_ID})()

    with patch("app.commands.inputs.trip_service.get_active_trip", new_callable=AsyncMock) as mock_trip, \
         patch("app.commands.inputs.expense_repository.get", new_callable=AsyncMock) as mock_get, \
         patch("app.commands.inputs.expense_repository.list_splits", new_callable=AsyncMock) as mock_splits, \
         patch("app.commands.inputs.expense_repository.replace_splits", new_callable=AsyncMock) as mock_replace, \
         _patch_end():
        mock_trip.return_value = trip
        mock_get.return_value = expense
        mock_splits.return_value = []

        await inputs._handle_edit_name(ctx, session, EXPENSE_ID, "edit")

    mock_replace.assert_called_once()
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        77,
        f"{messages.EXPENSE_UPDATED}\n\n{messages.EDIT_MENU_PROMPT}",
        reply_markup=inputs.keyboards.edit_menu(EXPENSE_ID),
        parse_mode=None,
    )


async def test_split_amount_mismatch_edits_existing_prompt_instead_of_sending_new_message():
    ctx = make_ctx(raw_text="@alice 10 @bob 20")
    session = make_session("edit_expense", "split_amount", payload={"expense_id": EXPENSE_ID})
    session.callback_message_id = 77

    expense = type("Expense", (), {"amount": Decimal("200.00"), "is_deleted": False})()
    trip = type("Trip", (), {"trip_id": TRIP_ID})()

    with patch("app.commands.inputs.trip_service.get_active_trip", new_callable=AsyncMock) as mock_trip, \
         patch("app.commands.inputs.expense_repository.get", new_callable=AsyncMock) as mock_get, \
         patch("app.commands.inputs.expense_service.replace_split_amounts", new_callable=AsyncMock) as mock_replace:
        mock_trip.return_value = trip
        mock_get.return_value = expense
        mock_replace.side_effect = inputs.ExpenseError("amount_mismatch")

        await inputs._handle_split_amount(ctx, session, EXPENSE_ID, "direct")

    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        77,
        messages.amount_split_mismatch(Decimal("30.00"), Decimal("200.00")),
        reply_markup=None,
        parse_mode=None,
    )
    ctx.client.send_message.assert_not_called()


async def test_split_amount_success_in_edit_flow_returns_to_edit_menu():
    ctx = make_ctx(raw_text="@alice 120 @bob 80")
    session = make_session("edit_expense", "split_amount", payload={"expense_id": EXPENSE_ID})
    session.callback_message_id = 77

    expense = type("Expense", (), {"amount": Decimal("200.00"), "is_deleted": False})()
    trip = type("Trip", (), {"trip_id": TRIP_ID})()

    with patch("app.commands.inputs.trip_service.get_active_trip", new_callable=AsyncMock) as mock_trip, \
         patch("app.commands.inputs.expense_repository.get", new_callable=AsyncMock) as mock_get, \
         patch("app.commands.inputs.expense_service.replace_split_amounts", new_callable=AsyncMock) as mock_replace, \
         _patch_end():
        mock_trip.return_value = trip
        mock_get.return_value = expense

        await inputs._handle_split_amount(ctx, session, EXPENSE_ID, "edit")

    mock_replace.assert_called_once()
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        77,
        f"{messages.EXPENSE_UPDATED}\n\n{messages.EDIT_MENU_PROMPT}",
        reply_markup=inputs.keyboards.edit_menu(EXPENSE_ID),
        parse_mode=None,
    )


async def test_split_amount_success_in_direct_flow_edits_existing_prompt_with_success():
    ctx = make_ctx(raw_text="@alice 120 @bob 80")
    session = make_session("edit_expense", "split_amount", payload={"expense_id": EXPENSE_ID})
    session.callback_message_id = 77

    expense = type("Expense", (), {"amount": Decimal("200.00"), "is_deleted": False})()
    trip = type("Trip", (), {"trip_id": TRIP_ID})()

    with patch("app.commands.inputs.trip_service.get_active_trip", new_callable=AsyncMock) as mock_trip, \
         patch("app.commands.inputs.expense_repository.get", new_callable=AsyncMock) as mock_get, \
         patch("app.commands.inputs.expense_service.replace_split_amounts", new_callable=AsyncMock) as mock_replace, \
         _patch_end():
        mock_trip.return_value = trip
        mock_get.return_value = expense

        await inputs._handle_split_amount(ctx, session, EXPENSE_ID, "direct")

    mock_replace.assert_called_once()
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        77,
        messages.EXPENSE_UPDATED,
        reply_markup=None,
        parse_mode=None,
    )
