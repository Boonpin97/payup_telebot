"""Tests for inline-button callback handling."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time

from app.commands import callbacks
from app.commands.callbacks import SRC_DIRECT, SRC_EDIT
from app.telegram import keyboards, messages
from app.utils.timeouts import utcnow

from .conftest import (
    CHAT_ID,
    EXPENSE_ID,
    TRIP_ID,
    USER_A_ID,
    USER_A_NAME,
    make_callback_ctx,
    make_expense,
    make_session,
    make_split,
    make_trip,
)


def _recent_unix() -> int:
    return int(utcnow().timestamp())


def _expired_unix() -> int:
    return int(utcnow().timestamp()) - 300


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_expense_get():
    return patch("app.repositories.expense_repository.get", new_callable=AsyncMock)


def _patch_expense_delete():
    return patch("app.services.expense_service.delete_expense", new_callable=AsyncMock)


def _patch_session_create():
    return patch("app.services.session_service.create", new_callable=AsyncMock)


def _patch_trip_delete():
    return patch("app.services.trip_service.delete_trip", new_callable=AsyncMock)


def _patch_trip_switch():
    return patch("app.services.trip_service.switch_active_trip", new_callable=AsyncMock)


# ---------------------------------------------------------------------------
# Expired message
# ---------------------------------------------------------------------------


async def test_expired_message_sends_session_expired_alert():
    ctx = make_callback_ctx(data=f"{keyboards.EXPENSE_EDIT}:{EXPENSE_ID}")
    await callbacks.handle(ctx, _expired_unix())
    ctx.client.answer_callback_query.assert_called_once()
    call_kw = ctx.client.answer_callback_query.call_args[1]
    assert call_kw.get("show_alert") is True
    assert messages.SESSION_EXPIRED in call_kw.get("text", "")


async def test_expired_message_attempts_to_clear_buttons():
    ctx = make_callback_ctx(data=f"{keyboards.EXPENSE_EDIT}:{EXPENSE_ID}")
    await callbacks.handle(ctx, _expired_unix())
    ctx.client.edit_message_reply_markup.assert_called_once()


# ---------------------------------------------------------------------------
# Expense delete
# ---------------------------------------------------------------------------


async def test_expense_delete_callback_no_active_trip():
    ctx = make_callback_ctx(data=f"{keyboards.EXPENSE_DELETE}:{EXPENSE_ID}")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await callbacks.handle(ctx, _recent_unix())
    ctx.client.answer_callback_query.assert_called()
    call_kw = ctx.client.answer_callback_query.call_args[1]
    assert call_kw.get("show_alert") is True


async def test_expense_delete_callback_deletes_and_confirms():
    ctx = make_callback_ctx(data=f"{keyboards.EXPENSE_DELETE}:{EXPENSE_ID}")
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_expense_delete() as mock_del:
        mock_trip.return_value = trip
        await callbacks.handle(ctx, _recent_unix())

    mock_del.assert_called_once_with(CHAT_ID, TRIP_ID, EXPENSE_ID)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.EXPENSE_DELETED_SHORT)


# ---------------------------------------------------------------------------
# Delete payment pick (delpay callback)
# ---------------------------------------------------------------------------


async def test_delete_payment_pick_no_active_trip():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_PAYMENT_PICK}:{EXPENSE_ID}")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await callbacks.handle(ctx, _recent_unix())
    ctx.client.answer_callback_query.assert_called()
    assert ctx.client.answer_callback_query.call_args[1].get("show_alert") is True


async def test_delete_payment_pick_expense_already_deleted():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_PAYMENT_PICK}:{EXPENSE_ID}")
    trip = make_trip()
    expense = make_expense()
    expense.is_deleted = True

    with _patch_trip() as mock_trip, _patch_expense_get() as mock_get:
        mock_trip.return_value = trip
        mock_get.return_value = expense
        await callbacks.handle(ctx, _recent_unix())

    ctx.client.answer_callback_query.assert_called()
    assert ctx.client.answer_callback_query.call_args[1].get("show_alert") is True


async def test_delete_payment_pick_deletes_expense():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_PAYMENT_PICK}:{EXPENSE_ID}")
    trip = make_trip()
    expense = make_expense(name="pasta", amount="10.00")

    with _patch_trip() as mock_trip, \
         _patch_expense_get() as mock_get, \
         _patch_expense_delete() as mock_del:
        mock_trip.return_value = trip
        mock_get.return_value = expense
        await callbacks.handle(ctx, _recent_unix())

    mock_del.assert_called_once_with(CHAT_ID, TRIP_ID, EXPENSE_ID)


# ---------------------------------------------------------------------------
# Switch trip pick
# ---------------------------------------------------------------------------


async def test_switch_trip_pick_switches_active_trip():
    ctx = make_callback_ctx(data=f"{keyboards.SWITCH_TRIP_PICK}:{TRIP_ID}")
    trip = make_trip()

    with _patch_trip_switch() as mock_switch, \
         patch("app.services.member_service.active_usernames", new_callable=AsyncMock) as mock_members:
        mock_switch.return_value = trip
        mock_members.return_value = ["alice"]
        await callbacks.handle(ctx, _recent_unix())

    mock_switch.assert_called_once_with(CHAT_ID, TRIP_ID)
    ctx.client.send_message.assert_called_once()
    assert "BKK" in ctx.client.send_message.call_args[0][1]


async def test_switch_trip_pick_trip_no_longer_exists():
    ctx = make_callback_ctx(data=f"{keyboards.SWITCH_TRIP_PICK}:deleted-trip")
    with _patch_trip_switch() as mock_switch:
        mock_switch.return_value = None
        await callbacks.handle(ctx, _recent_unix())
    ctx.client.send_message.assert_called_once()
    assert "no longer" in ctx.client.send_message.call_args[0][1].lower()


# ---------------------------------------------------------------------------
# Delete trip flow (pick → confirm / cancel)
# ---------------------------------------------------------------------------


async def test_delete_trip_pick_shows_confirmation_keyboard():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_TRIP_PICK}:{TRIP_ID}")
    trip = make_trip()

    with patch("app.repositories.trip_repository.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = trip
        await callbacks.handle(ctx, _recent_unix())

    ctx.client.send_message.assert_called_once()
    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    all_data = [btn["callback_data"] for row in keyboard["inline_keyboard"] for btn in row]
    assert any(d.startswith(keyboards.DELETE_TRIP_CONFIRM) for d in all_data)
    assert any(d.startswith(keyboards.DELETE_TRIP_CANCEL) for d in all_data)


async def test_delete_trip_pick_trip_not_found():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_TRIP_PICK}:missing")
    with patch("app.repositories.trip_repository.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        await callbacks.handle(ctx, _recent_unix())
    ctx.client.send_message.assert_called_once()
    assert "no longer" in ctx.client.send_message.call_args[0][1].lower()


async def test_delete_trip_confirm_deletes_trip():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_TRIP_CONFIRM}:{TRIP_ID}")
    trip = make_trip()

    with _patch_trip_delete() as mock_del:
        mock_del.return_value = trip
        await callbacks.handle(ctx, _recent_unix())

    mock_del.assert_called_once_with(CHAT_ID, TRIP_ID)
    ctx.client.send_message.assert_called_once()
    text = ctx.client.send_message.call_args[0][1]
    assert "BKK" in text or "deleted" in text.lower()


async def test_delete_trip_confirm_trip_not_found():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_TRIP_CONFIRM}:ghost")
    with _patch_trip_delete() as mock_del:
        mock_del.return_value = None
        await callbacks.handle(ctx, _recent_unix())
    ctx.client.send_message.assert_called_once()
    assert "no longer" in ctx.client.send_message.call_args[0][1].lower()


async def test_delete_trip_cancel_sends_cancelled():
    ctx = make_callback_ctx(data=f"{keyboards.DELETE_TRIP_CANCEL}:{TRIP_ID}")
    await callbacks.handle(ctx, _recent_unix())
    ctx.client.send_message.assert_called_once_with(CHAT_ID, "Cancelled.")


# ---------------------------------------------------------------------------
# Split equal callback
# ---------------------------------------------------------------------------


async def test_split_equal_no_active_trip():
    ctx = make_callback_ctx(data=f"{keyboards.SPLIT_EQUAL}:{EXPENSE_ID}")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await callbacks.handle(ctx, _recent_unix())
    assert ctx.client.answer_callback_query.call_args[1].get("show_alert") is True


async def test_split_equal_updates_expense():
    ctx = make_callback_ctx(data=f"{keyboards.SPLIT_EQUAL}:{EXPENSE_ID}")
    trip = make_trip()
    expense = make_expense(participants=["alice", "bob"])
    split = make_split("alice", "5.00")

    with _patch_trip() as mock_trip, \
         _patch_expense_get() as mock_get, \
         patch("app.services.expense_service.replace_split_equal", new_callable=AsyncMock) as mock_split:
        mock_trip.return_value = trip
        mock_get.return_value = expense
        mock_split.return_value = [split, make_split("bob", "5.00")]
        await callbacks.handle(ctx, _recent_unix())

    mock_split.assert_called_once()
    ctx.client.send_message.assert_called_once()


async def test_expense_partial_edits_message_to_split_type_menu():
    ctx = make_callback_ctx(data=f"{keyboards.EXPENSE_PARTIAL}:{EXPENSE_ID}")

    await callbacks.handle(ctx, _recent_unix())

    ctx.client.answer_callback_query.assert_called_once_with(ctx.callback_query_id)
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        ctx.message_id,
        "Choose a split type:",
        reply_markup=keyboards.partial_split_menu(EXPENSE_ID),
        parse_mode=None,
    )


async def test_edit_partial_edits_message_to_split_type_menu():
    ctx = make_callback_ctx(data=f"{keyboards.EDIT_PARTIAL}:{EXPENSE_ID}")

    await callbacks.handle(ctx, _recent_unix())

    ctx.client.answer_callback_query.assert_called_once_with(ctx.callback_query_id)
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        ctx.message_id,
        "Choose a split type:",
        reply_markup=keyboards.partial_split_menu(EXPENSE_ID),
        parse_mode=None,
    )


# ---------------------------------------------------------------------------
# Edit menu — start text-input sessions
# ---------------------------------------------------------------------------


async def test_edit_name_starts_session_with_edit_name_step():
    ctx = make_callback_ctx(data=f"{keyboards.EDIT_NAME}:{EXPENSE_ID}")
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("edit_expense", "edit_name")

    with patch("app.services.session_service.create", side_effect=capture):
        await callbacks.handle(ctx, _recent_unix())

    assert captured[0]["step"] == "edit_name"
    assert captured[0]["payload"]["expense_id"] == EXPENSE_ID
    assert captured[0]["callback_message_id"] == ctx.message_id
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        ctx.message_id,
        messages.EDIT_ASK_NAME,
        reply_markup=None,
        parse_mode=None,
    )


async def test_edit_amount_starts_session_with_edit_amount_step():
    ctx = make_callback_ctx(data=f"{keyboards.EDIT_AMOUNT}:{EXPENSE_ID}")
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("edit_expense", "edit_amount")

    with patch("app.services.session_service.create", side_effect=capture):
        await callbacks.handle(ctx, _recent_unix())

    assert captured[0]["step"] == "edit_amount"
    assert captured[0]["callback_message_id"] == ctx.message_id
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        ctx.message_id,
        messages.EDIT_ASK_AMOUNT,
        reply_markup=None,
        parse_mode=None,
    )


async def test_edit_people_starts_session_with_edit_people_step():
    ctx = make_callback_ctx(data=f"{keyboards.EDIT_PEOPLE}:{EXPENSE_ID}")
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("edit_expense", "edit_people")

    with patch("app.services.session_service.create", side_effect=capture):
        await callbacks.handle(ctx, _recent_unix())

    assert captured[0]["step"] == "edit_people"
    assert captured[0]["callback_message_id"] == ctx.message_id
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        ctx.message_id,
        messages.EDIT_ASK_PEOPLE,
        reply_markup=None,
        parse_mode="Markdown",
    )


async def test_split_amount_starts_session_with_src_direct():
    ctx = make_callback_ctx(data=f"{keyboards.SPLIT_AMOUNT}:{EXPENSE_ID}")
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("edit_expense", "split_amount")

    with patch("app.services.session_service.create", side_effect=capture):
        await callbacks.handle(ctx, _recent_unix())

    assert captured[0]["payload"]["source"] == SRC_DIRECT
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        ctx.message_id,
        messages.PARTIAL_AMOUNT_PROMPT,
        reply_markup=None,
        parse_mode="Markdown",
    )


async def test_split_percent_starts_session_with_src_direct():
    ctx = make_callback_ctx(data=f"{keyboards.SPLIT_PERCENT}:{EXPENSE_ID}")
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("edit_expense", "split_percent")

    with patch("app.services.session_service.create", side_effect=capture):
        await callbacks.handle(ctx, _recent_unix())

    assert captured[0]["payload"]["source"] == SRC_DIRECT
    ctx.client.edit_message_text.assert_called_once_with(
        CHAT_ID,
        ctx.message_id,
        messages.PARTIAL_PERCENT_PROMPT,
        reply_markup=None,
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Unknown callback action — should answer without error
# ---------------------------------------------------------------------------


async def test_unknown_callback_action_answers_without_error():
    ctx = make_callback_ctx(data="totally_unknown_action:abc")
    await callbacks.handle(ctx, _recent_unix())
    ctx.client.answer_callback_query.assert_called_once_with(ctx.callback_query_id)
