"""Tests for the /delete_payment command."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.commands import delete_payment
from app.telegram import keyboards, messages

from .conftest import CHAT_ID, EXPENSE_ID, TRIP_ID, make_ctx, make_expense, make_trip


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_expenses():
    return patch("app.repositories.expense_repository.list_active", new_callable=AsyncMock)


async def test_handle_no_active_trip_sends_no_active_trip():
    ctx = make_ctx()
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await delete_payment.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_no_expenses_sends_empty_message():
    ctx = make_ctx()
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_expenses() as mock_expenses:
        mock_trip.return_value = trip
        mock_expenses.return_value = []
        await delete_payment.handle(ctx)

    ctx.client.send_message.assert_called_once()
    assert "no expenses" in ctx.client.send_message.call_args[0][1].lower()


async def test_handle_with_expenses_sends_keyboard():
    ctx = make_ctx()
    trip = make_trip()
    expenses = [make_expense(name="pasta"), make_expense(expense_id="exp-002", name="taxi")]

    with _patch_trip() as mock_trip, _patch_expenses() as mock_expenses:
        mock_trip.return_value = trip
        mock_expenses.return_value = expenses
        await delete_payment.handle(ctx)

    ctx.client.send_message.assert_called_once()
    call_kwargs = ctx.client.send_message.call_args[1]
    assert "reply_markup" in call_kwargs
    keyboard = call_kwargs["reply_markup"]
    assert "inline_keyboard" in keyboard


async def test_handle_keyboard_contains_all_expense_labels():
    ctx = make_ctx()
    trip = make_trip()
    expenses = [
        make_expense(expense_id="e1", name="pasta", amount="10.00"),
        make_expense(expense_id="e2", name="taxi", amount="25.50"),
    ]

    with _patch_trip() as mock_trip, _patch_expenses() as mock_expenses:
        mock_trip.return_value = trip
        mock_expenses.return_value = expenses
        await delete_payment.handle(ctx)

    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    all_labels = [
        btn["text"]
        for row in keyboard["inline_keyboard"]
        for btn in row
    ]
    assert any("pasta" in lbl for lbl in all_labels)
    assert any("taxi" in lbl for lbl in all_labels)


async def test_handle_keyboard_callback_data_uses_delpay_prefix():
    ctx = make_ctx()
    trip = make_trip()
    expenses = [make_expense()]

    with _patch_trip() as mock_trip, _patch_expenses() as mock_expenses:
        mock_trip.return_value = trip
        mock_expenses.return_value = expenses
        await delete_payment.handle(ctx)

    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    all_data = [
        btn["callback_data"]
        for row in keyboard["inline_keyboard"]
        for btn in row
    ]
    assert all(d.startswith(keyboards.DELETE_PAYMENT_PICK) for d in all_data)
