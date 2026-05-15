"""Tests for /settle command."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.commands import settle
from app.services.expense_service import ExpenseError
from app.telegram import messages

from .conftest import CHAT_ID, TRIP_ID, USER_A_ID, USER_A_NAME, make_ctx, make_trip


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_add_settlement():
    return patch("app.services.expense_service.add_settlement", new_callable=AsyncMock)


def _patch_active_usernames():
    return patch("app.services.member_service.active_usernames", new_callable=AsyncMock)


def _patch_add_members():
    return patch("app.services.member_service.add_members", new_callable=AsyncMock)


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------


async def test_handle_no_username_sends_error():
    ctx = make_ctx(username="", args_text="@bob 50")
    await settle.handle(ctx)
    ctx.client.send_message.assert_called_once()
    assert "username" in ctx.client.send_message.call_args[0][1].lower()


async def test_handle_no_args_sends_usage():
    ctx = make_ctx(args_text="")
    await settle.handle(ctx)
    ctx.client.send_message.assert_called_once()
    assert "/settle" in ctx.client.send_message.call_args[0][1]


async def test_handle_invalid_format_sends_usage():
    ctx = make_ctx(args_text="@bob")  # missing amount
    await settle.handle(ctx)
    ctx.client.send_message.assert_called_once()
    assert "/settle" in ctx.client.send_message.call_args[0][1]


async def test_handle_invalid_amount_sends_usage():
    ctx = make_ctx(args_text="@bob abc")
    await settle.handle(ctx)
    ctx.client.send_message.assert_called_once()
    assert "/settle" in ctx.client.send_message.call_args[0][1]


async def test_handle_negative_amount_sends_usage():
    ctx = make_ctx(args_text="@bob -10")
    await settle.handle(ctx)
    ctx.client.send_message.assert_called_once()
    assert "/settle" in ctx.client.send_message.call_args[0][1]


async def test_handle_settle_with_self_sends_error():
    ctx = make_ctx(username="alice", args_text="@alice 50")
    await settle.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.SETTLE_SELF_ERROR)


async def test_handle_no_active_trip_sends_no_active_trip():
    ctx = make_ctx(args_text="@bob 50")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await settle.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_recipient_not_in_trip_sends_unknown_member():
    ctx = make_ctx(username="alice", args_text="@ghost 50")
    trip = make_trip()
    with _patch_trip() as mock_trip, _patch_active_usernames() as mock_members:
        mock_trip.return_value = trip
        mock_members.return_value = ["alice"]  # ghost missing
        await settle.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "ghost" in text


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_handle_valid_creates_settlement():
    ctx = make_ctx(username="alice", args_text="@bob 50.00")
    trip = make_trip()
    with _patch_trip() as mock_trip, \
         _patch_active_usernames() as mock_members, \
         _patch_add_members(), \
         _patch_add_settlement() as mock_settle:
        mock_trip.return_value = trip
        mock_members.return_value = ["alice", "bob"]
        await settle.handle(ctx)
    mock_settle.assert_called_once()
    kw = mock_settle.call_args[1]
    assert kw["payer_username"] == "alice"
    assert kw["recipient_username"] == "bob"
    assert kw["amount"] == Decimal("50.00")


async def test_handle_valid_sends_confirmation():
    ctx = make_ctx(username="alice", args_text="@bob 30")
    trip = make_trip()
    with _patch_trip() as mock_trip, \
         _patch_active_usernames() as mock_members, \
         _patch_add_members(), \
         _patch_add_settlement():
        mock_trip.return_value = trip
        mock_members.return_value = ["alice", "bob"]
        await settle.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "@alice" in text
    assert "@bob" in text
    assert "30" in text


async def test_handle_payer_not_in_trip_auto_adds():
    ctx = make_ctx(username="alice", args_text="@bob 20")
    trip = make_trip()
    with _patch_trip() as mock_trip, \
         _patch_active_usernames() as mock_members, \
         _patch_add_members() as mock_add, \
         _patch_add_settlement():
        mock_trip.return_value = trip
        mock_members.return_value = ["bob"]  # alice missing
        await settle.handle(ctx)
    mock_add.assert_called_once_with(CHAT_ID, TRIP_ID, ["alice"])


async def test_handle_payer_already_in_trip_no_auto_add():
    ctx = make_ctx(username="alice", args_text="@bob 20")
    trip = make_trip()
    with _patch_trip() as mock_trip, \
         _patch_active_usernames() as mock_members, \
         _patch_add_members() as mock_add, \
         _patch_add_settlement():
        mock_trip.return_value = trip
        mock_members.return_value = ["alice", "bob"]
        await settle.handle(ctx)
    mock_add.assert_not_called()


async def test_handle_passes_correct_trip_and_group_ids():
    ctx = make_ctx(username="alice", args_text="@bob 10")
    trip = make_trip(trip_id="t-custom", trip_name="Custom")
    trip.group_id = "chat_100"
    with _patch_trip() as mock_trip, \
         _patch_active_usernames() as mock_members, \
         _patch_add_members(), \
         _patch_add_settlement() as mock_settle:
        mock_trip.return_value = trip
        mock_members.return_value = ["alice", "bob"]
        await settle.handle(ctx)
    kw = mock_settle.call_args[1]
    assert kw["trip_id"] == "t-custom"
    assert kw["group_id"] == "chat_100"


async def test_handle_expense_service_error_sends_unknown_member():
    ctx = make_ctx(username="alice", args_text="@bob 10")
    trip = make_trip()
    with _patch_trip() as mock_trip, \
         _patch_active_usernames() as mock_members, \
         _patch_add_members(), \
         _patch_add_settlement() as mock_settle:
        mock_trip.return_value = trip
        mock_members.return_value = ["alice", "bob"]
        mock_settle.side_effect = ExpenseError("bob")
        await settle.handle(ctx)
    text = ctx.client.send_message.call_args[0][1]
    assert "bob" in text
