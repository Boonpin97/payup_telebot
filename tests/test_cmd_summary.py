"""Tests for the /summary command."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.commands import summary
from app.services.expense_service import TripSummary
from app.telegram import messages

from .conftest import CHAT_ID, TRIP_NAME, make_ctx, make_trip


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_summary():
    return patch("app.services.expense_service.compute_summary", new_callable=AsyncMock)


def _empty_summary(trip_name: str = TRIP_NAME) -> TripSummary:
    return TripSummary(
        members=[],
        total_spent=Decimal("0.00"),
        paid_by={},
        owed_by={},
        net_balance={},
        settlements=[],
    )


def _populated_summary() -> TripSummary:
    return TripSummary(
        members=["alice", "bob"],
        total_spent=Decimal("30.00"),
        paid_by={"alice": Decimal("30.00"), "bob": Decimal("0.00")},
        owed_by={"alice": Decimal("15.00"), "bob": Decimal("15.00")},
        net_balance={"alice": Decimal("15.00"), "bob": Decimal("-15.00")},
        settlements=[("bob", "alice", Decimal("15.00"))],
    )


async def test_handle_no_active_trip_sends_no_active_trip():
    ctx = make_ctx()
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await summary.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_empty_trip_sends_summary_with_zero_total():
    ctx = make_ctx()
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_summary() as mock_summary:
        mock_trip.return_value = trip
        mock_summary.return_value = _empty_summary()
        await summary.handle(ctx)

    ctx.client.send_message.assert_called_once()
    text = ctx.client.send_message.call_args[0][1]
    assert TRIP_NAME in text


async def test_handle_populated_trip_sends_balances_and_settlements():
    ctx = make_ctx()
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_summary() as mock_summary:
        mock_trip.return_value = trip
        mock_summary.return_value = _populated_summary()
        await summary.handle(ctx)

    text = ctx.client.send_message.call_args[0][1]
    assert "alice" in text
    assert "bob" in text
    assert "30.00" in text  # total spent
    assert "@alice spent 15.00" in text
    assert "@bob spent 15.00" in text
    assert "Net Balance:" not in text
    assert "Members:" not in text
    assert text.index("Spent:") < text.index("Paid:")


async def test_handle_everyone_settled_shows_settled_message():
    ctx = make_ctx()
    trip = make_trip()
    s = TripSummary(
        members=["alice", "bob"],
        total_spent=Decimal("20.00"),
        paid_by={"alice": Decimal("10.00"), "bob": Decimal("10.00")},
        owed_by={"alice": Decimal("10.00"), "bob": Decimal("10.00")},
        net_balance={"alice": Decimal("0.00"), "bob": Decimal("0.00")},
        settlements=[],
    )

    with _patch_trip() as mock_trip, _patch_summary() as mock_summary:
        mock_trip.return_value = trip
        mock_summary.return_value = s
        await summary.handle(ctx)

    text = ctx.client.send_message.call_args[0][1]
    assert "settled" in text.lower()


async def test_handle_calls_compute_summary_with_correct_trip_id():
    ctx = make_ctx()
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_summary() as mock_summary:
        mock_trip.return_value = trip
        mock_summary.return_value = _empty_summary()
        await summary.handle(ctx)

    mock_summary.assert_called_once_with(CHAT_ID, trip.trip_id)


async def test_handle_shows_each_persons_total_trip_spend():
    ctx = make_ctx()
    trip = make_trip()
    s = TripSummary(
        members=["alice", "bob"],
        total_spent=Decimal("300.00"),
        paid_by={"alice": Decimal("200.00"), "bob": Decimal("100.00")},
        owed_by={"alice": Decimal("100.00"), "bob": Decimal("200.00")},
        net_balance={"alice": Decimal("100.00"), "bob": Decimal("-100.00")},
        settlements=[("bob", "alice", Decimal("100.00"))],
    )

    with _patch_trip() as mock_trip, _patch_summary() as mock_summary:
        mock_trip.return_value = trip
        mock_summary.return_value = s
        await summary.handle(ctx)

    text = ctx.client.send_message.call_args[0][1]
    assert "@alice spent 100.00" in text
    assert "@bob spent 200.00" in text
    assert "Net Balance:" not in text
    assert "Members:" not in text
    assert text.index("Spent:") < text.index("Paid:")
