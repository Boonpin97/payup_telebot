"""Tests for /list_expenses command."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.commands import list_expenses
from app.telegram import messages

from .conftest import CHAT_ID, TRIP_ID, TRIP_NAME, make_ctx, make_expense, make_trip


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_expenses():
    return patch("app.repositories.expense_repository.list_active", new_callable=AsyncMock)


async def test_handle_no_active_trip():
    ctx = make_ctx()
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await list_expenses.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_no_expenses_sends_empty_message():
    ctx = make_ctx()
    trip = make_trip()
    with _patch_trip() as mock_trip, _patch_expenses() as mock_exp:
        mock_trip.return_value = trip
        mock_exp.return_value = []
        await list_expenses.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "no expenses" in text.lower()


async def test_handle_lists_expense_names_and_amounts():
    ctx = make_ctx()
    trip = make_trip()
    expenses = [
        make_expense(name="pasta", amount="10.00"),
        make_expense(expense_id="exp-002", name="taxi", amount="25.50"),
    ]
    with _patch_trip() as mock_trip, _patch_expenses() as mock_exp:
        mock_trip.return_value = trip
        mock_exp.return_value = expenses
        await list_expenses.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "pasta" in text
    assert "10.00" in text
    assert "taxi" in text
    assert "25.50" in text


async def test_handle_shows_payer_for_regular_expense():
    ctx = make_ctx()
    trip = make_trip()
    expenses = [make_expense(name="dinner", payer="alice")]
    with _patch_trip() as mock_trip, _patch_expenses() as mock_exp:
        mock_trip.return_value = trip
        mock_exp.return_value = expenses
        await list_expenses.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "@alice" in text


async def test_handle_shows_trip_name_in_header():
    ctx = make_ctx()
    trip = make_trip(trip_name="Japan 2026")
    with _patch_trip() as mock_trip, _patch_expenses() as mock_exp:
        mock_trip.return_value = trip
        mock_exp.return_value = [make_expense()]
        await list_expenses.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "Japan 2026" in text


async def test_handle_shows_total_spent_excluding_settlements():
    ctx = make_ctx()
    trip = make_trip()
    regular = make_expense(name="lunch", amount="30.00")
    settlement = make_expense(expense_id="s1", name="Settlement", amount="10.00")
    settlement.is_settlement = True
    with _patch_trip() as mock_trip, _patch_expenses() as mock_exp:
        mock_trip.return_value = trip
        mock_exp.return_value = [regular, settlement]
        await list_expenses.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "30.00" in text   # total should be 30, not 40
    assert "Total spent: 30.00" in text


async def test_handle_settlement_shows_arrow_format():
    ctx = make_ctx()
    trip = make_trip()
    settlement = make_expense(
        expense_id="s1", name="Settlement", amount="15.00",
        payer="alice", participants=["bob"],
    )
    settlement.is_settlement = True
    with _patch_trip() as mock_trip, _patch_expenses() as mock_exp:
        mock_trip.return_value = trip
        mock_exp.return_value = [settlement]
        await list_expenses.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "[Settlement]" in text
    assert "@alice" in text
    assert "@bob" in text
    assert "→" in text


async def test_handle_numbered_list_starts_at_one():
    ctx = make_ctx()
    trip = make_trip()
    expenses = [make_expense(name="coffee"), make_expense(expense_id="e2", name="lunch")]
    with _patch_trip() as mock_trip, _patch_expenses() as mock_exp:
        mock_trip.return_value = trip
        mock_exp.return_value = expenses
        await list_expenses.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "1." in text
    assert "2." in text
