"""Tests for /settle command."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.commands import settle
from app.services.expense_service import ExpenseError, TripSummary
from app.telegram import keyboards, messages

from .conftest import CHAT_ID, TRIP_ID, USER_A_ID, USER_A_NAME, make_ctx, make_trip


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_add_settlement():
    return patch("app.services.expense_service.add_settlement", new_callable=AsyncMock)


def _patch_active_usernames():
    return patch("app.services.member_service.active_usernames", new_callable=AsyncMock)


def _patch_add_members():
    return patch("app.services.member_service.add_members", new_callable=AsyncMock)


def _patch_compute_summary():
    return patch("app.services.expense_service.compute_summary", new_callable=AsyncMock)


def _summary(settlements: list[tuple[str, str, Decimal]]) -> TripSummary:
    return TripSummary(
        members=[],
        total_spent=Decimal("0"),
        paid_by={},
        owed_by={},
        net_balance={},
        settlements=settlements,
    )


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------


async def test_handle_no_username_sends_error():
    ctx = make_ctx(username="", args_text="@bob 50")
    await settle.handle(ctx)
    ctx.client.send_message.assert_called_once()
    assert "username" in ctx.client.send_message.call_args[0][1].lower()


async def test_handle_no_args_shows_picker_with_settlements():
    ctx = make_ctx(args_text="")
    trip = make_trip()
    settlements = [("alice", "bob", Decimal("12.34")), ("carol", "bob", Decimal("5.00"))]
    with _patch_trip() as mock_trip, _patch_compute_summary() as mock_summary:
        mock_trip.return_value = trip
        mock_summary.return_value = _summary(settlements)
        await settle.handle(ctx)
    assert ctx.client.send_message.call_args[0][1] == messages.PICK_DEBT_TO_SETTLE
    markup = ctx.client.send_message.call_args[1]["reply_markup"]
    rows = markup["inline_keyboard"]
    assert len(rows) == 2
    assert rows[0][0]["callback_data"] == f"{keyboards.SETTLE_PICK}:0"
    assert rows[1][0]["callback_data"] == f"{keyboards.SETTLE_PICK}:1"
    assert "@alice" in rows[0][0]["text"] and "@bob" in rows[0][0]["text"]


async def test_handle_no_args_no_active_trip_uses_no_active_trip_message():
    ctx = make_ctx(args_text="")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await settle.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_no_args_all_settled_replies_all_settled():
    ctx = make_ctx(args_text="")
    trip = make_trip()
    with _patch_trip() as mock_trip, _patch_compute_summary() as mock_summary:
        mock_trip.return_value = trip
        mock_summary.return_value = _summary([])
        await settle.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ALL_SETTLED)


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


# ---------------------------------------------------------------------------
# Settle picker callback
# ---------------------------------------------------------------------------


def _patch_list_active_members():
    return patch("app.repositories.member_repository.list_active", new_callable=AsyncMock)


def _patch_callbacks_compute_summary():
    return patch(
        "app.commands.callbacks.expense_service.compute_summary",
        new_callable=AsyncMock,
    )


def _patch_callbacks_trip():
    return patch(
        "app.commands.callbacks.trip_service.get_active_trip",
        new_callable=AsyncMock,
    )


def _patch_callbacks_add_settlement():
    return patch(
        "app.commands.callbacks.expense_service.add_settlement",
        new_callable=AsyncMock,
    )


def _patch_callbacks_list_members():
    return patch(
        "app.commands.callbacks.member_repository.list_active",
        new_callable=AsyncMock,
    )


async def _dispatch_pick(data: str):
    """Run the callback dispatcher with a fresh timestamp (not expired)."""
    from app.commands import callbacks
    from app.utils.timeouts import utcnow
    from .conftest import make_callback_ctx

    ctx = make_callback_ctx(data=data)
    await callbacks.handle(ctx, int(utcnow().timestamp()))
    return ctx


async def test_settle_pick_records_settlement_for_current_debt():
    trip = make_trip()
    settlements = [
        ("alice", "bob", Decimal("12.34")),
        ("carol", "bob", Decimal("5.00")),
    ]
    debtor_member = MagicMock()
    debtor_member.username = "alice"
    debtor_member.telegram_user_id = 1001

    with _patch_callbacks_trip() as mock_trip, \
         _patch_callbacks_compute_summary() as mock_summary, \
         _patch_callbacks_list_members() as mock_members, \
         _patch_callbacks_add_settlement() as mock_settle:
        mock_trip.return_value = trip
        mock_summary.return_value = _summary(settlements)
        mock_members.return_value = [debtor_member]
        ctx = await _dispatch_pick(f"{keyboards.SETTLE_PICK}:0")

    mock_settle.assert_called_once()
    kw = mock_settle.call_args[1]
    assert kw["payer_username"] == "alice"
    assert kw["recipient_username"] == "bob"
    assert kw["amount"] == Decimal("12.34")
    assert kw["payer_user_id"] == 1001
    text = ctx.client.send_message.call_args[0][1]
    assert "@alice" in text and "@bob" in text and "12.34" in text


async def test_settle_pick_out_of_range_shows_alert_and_no_settlement():
    trip = make_trip()
    with _patch_callbacks_trip() as mock_trip, \
         _patch_callbacks_compute_summary() as mock_summary, \
         _patch_callbacks_add_settlement() as mock_settle:
        mock_trip.return_value = trip
        mock_summary.return_value = _summary([("alice", "bob", Decimal("1.00"))])
        ctx = await _dispatch_pick(f"{keyboards.SETTLE_PICK}:5")
    mock_settle.assert_not_called()
    ctx.client.answer_callback_query.assert_called_once()
    kw = ctx.client.answer_callback_query.call_args[1]
    assert kw["show_alert"] is True
    assert "no longer" in (kw.get("text") or "").lower()


async def test_settle_pick_no_active_trip_shows_alert():
    with _patch_callbacks_trip() as mock_trip:
        mock_trip.return_value = None
        ctx = await _dispatch_pick(f"{keyboards.SETTLE_PICK}:0")
    ctx.client.answer_callback_query.assert_called_once()
    kw = ctx.client.answer_callback_query.call_args[1]
    assert kw["show_alert"] is True
    assert "No active trip" in (kw.get("text") or "")


async def test_settle_pick_invalid_index_is_silently_ignored():
    ctx = await _dispatch_pick(f"{keyboards.SETTLE_PICK}:notanumber")
    # No send_message; just a benign callback ack.
    ctx.client.send_message.assert_not_called()
