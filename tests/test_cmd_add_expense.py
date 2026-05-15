"""Tests for the /add_expense command (inline and prompted flows)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.commands import add_expense
from app.commands.add_expense import STEP_ASK_EXPENSE
from app.services.expense_service import CreatedExpense, ExpenseError
from app.telegram import messages

from .conftest import (
    CHAT_ID,
    EXPENSE_ID,
    TRIP_ID,
    USER_A_ID,
    USER_A_NAME,
    make_ctx,
    make_expense,
    make_session,
    make_split,
    make_trip,
)


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_expense_add():
    return patch("app.services.expense_service.add_expense", new_callable=AsyncMock)


def _patch_member_usernames():
    return patch("app.services.member_service.active_usernames", new_callable=AsyncMock)


def _patch_member_add():
    return patch("app.services.member_service.add_members", new_callable=AsyncMock)


def _patch_session_create():
    return patch("app.services.session_service.create", new_callable=AsyncMock)


def _patch_session_end():
    return patch("app.services.session_service.end", new_callable=AsyncMock)


def _make_created(expense=None, splits=None):
    exp = expense or make_expense()
    spl = splits or [make_split(USER_A_NAME)]
    return CreatedExpense(expense=exp, splits=spl)


# ---------------------------------------------------------------------------
# handle() — inline args path
# ---------------------------------------------------------------------------


async def test_handle_no_active_trip_sends_no_active_trip():
    ctx = make_ctx(args_text="pasta 10")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await add_expense.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_no_username_sends_error():
    ctx = make_ctx(username="", args_text="pasta 10")
    await add_expense.handle(ctx)
    ctx.client.send_message.assert_called_once()
    assert "username" in ctx.client.send_message.call_args[0][1].lower()


async def test_handle_inline_args_creates_expense_and_sends_confirmation():
    ctx = make_ctx(args_text="pasta 10")
    trip = make_trip()
    created = _make_created()

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members, \
         _patch_member_add(), \
         _patch_expense_add() as mock_add:
        mock_trip.return_value = trip
        mock_members.return_value = [USER_A_NAME]
        mock_add.return_value = created
        await add_expense.handle(ctx)

    mock_add.assert_called_once()
    ctx.client.send_message.assert_called_once()
    text = ctx.client.send_message.call_args[0][1]
    assert "pasta" in text


async def test_handle_inline_args_with_participants():
    ctx = make_ctx(args_text="dinner 30 @alice @bob")
    trip = make_trip()
    exp = make_expense(name="dinner", amount="30.00", participants=["alice", "bob"])
    splits = [make_split("alice", "15.00"), make_split("bob", "15.00")]
    created = CreatedExpense(expense=exp, splits=splits)

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members, \
         _patch_member_add(), \
         _patch_expense_add() as mock_add:
        mock_trip.return_value = trip
        mock_members.return_value = ["alice", "bob"]
        mock_add.return_value = created
        await add_expense.handle(ctx)

    kw = mock_add.call_args[1]
    assert sorted(kw["participants"]) == ["alice", "bob"]
    assert kw["amount"] == Decimal("30.00")


async def test_handle_inline_invalid_format_sends_usage():
    ctx = make_ctx(args_text="pasta")
    trip = make_trip()

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members:
        mock_trip.return_value = trip
        mock_members.return_value = [USER_A_NAME]
        await add_expense.handle(ctx)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ADD_EXPENSE_USAGE)


async def test_handle_inline_negative_amount_sends_usage():
    ctx = make_ctx(args_text="pasta -5")
    trip = make_trip()

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members:
        mock_trip.return_value = trip
        mock_members.return_value = [USER_A_NAME]
        await add_expense.handle(ctx)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ADD_EXPENSE_USAGE)


async def test_handle_inline_unknown_participant_sends_unknown_member():
    ctx = make_ctx(args_text="pasta 10 @ghost")
    trip = make_trip()

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members, \
         _patch_member_add(), \
         _patch_expense_add() as mock_add:
        mock_trip.return_value = trip
        mock_members.return_value = [USER_A_NAME]
        mock_add.side_effect = ExpenseError("ghost")
        await add_expense.handle(ctx)

    text = ctx.client.send_message.call_args[0][1]
    assert "ghost" in text


async def test_handle_inline_payer_not_in_trip_auto_adds():
    """Payer not currently in trip should be silently added before the expense."""
    ctx = make_ctx(username="alice", args_text="taxi 20")
    trip = make_trip()
    created = _make_created()

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members, \
         _patch_member_add() as mock_add_member, \
         _patch_expense_add() as mock_add:
        mock_trip.return_value = trip
        mock_members.return_value = ["bob"]  # alice missing
        mock_add.return_value = created
        await add_expense.handle(ctx)

    mock_add_member.assert_called_once_with(CHAT_ID, TRIP_ID, ["alice"])


async def test_handle_inline_payer_already_in_trip_no_auto_add():
    ctx = make_ctx(username="alice", args_text="taxi 20")
    trip = make_trip()
    created = _make_created()

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members, \
         _patch_member_add() as mock_add_member, \
         _patch_expense_add() as mock_add:
        mock_trip.return_value = trip
        mock_members.return_value = ["alice"]
        mock_add.return_value = created
        await add_expense.handle(ctx)

    mock_add_member.assert_not_called()


# ---------------------------------------------------------------------------
# handle() — no-args prompted path
# ---------------------------------------------------------------------------


async def test_handle_no_args_no_trip_sends_no_active_trip():
    ctx = make_ctx(args_text="", username="alice")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await add_expense.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_no_args_starts_prompt_session():
    ctx = make_ctx(args_text="", username="alice")
    trip = make_trip()
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("add_expense", STEP_ASK_EXPENSE)

    with _patch_trip() as mock_trip, \
         patch("app.services.session_service.create", side_effect=capture):
        mock_trip.return_value = trip
        await add_expense.handle(ctx)

    assert captured, "session_service.create not called"
    assert captured[0]["step"] == STEP_ASK_EXPENSE


async def test_handle_no_args_sends_ask_expense_prompt():
    ctx = make_ctx(args_text="", username="alice")
    trip = make_trip()

    with _patch_trip() as mock_trip, \
         patch("app.services.session_service.create", new_callable=AsyncMock) as mock_create:
        mock_trip.return_value = trip
        mock_create.return_value = make_session("add_expense", STEP_ASK_EXPENSE)
        await add_expense.handle(ctx)

    ctx.client.send_message.assert_called_once()
    assert ctx.client.send_message.call_args[0][1] == messages.ASK_EXPENSE


# ---------------------------------------------------------------------------
# handle_input() — prompted expense reply
# ---------------------------------------------------------------------------


async def test_handle_input_no_username_ends_session_and_errors():
    ctx = make_ctx(username="", raw_text="pasta 10")
    session = make_session("add_expense", STEP_ASK_EXPENSE)

    with patch("app.services.session_service.end", new_callable=AsyncMock):
        await add_expense.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once()
    assert "username" in ctx.client.send_message.call_args[0][1].lower()


async def test_handle_input_no_active_trip_ends_session():
    ctx = make_ctx(raw_text="pasta 10")
    session = make_session("add_expense", STEP_ASK_EXPENSE)

    with patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock) as mock_trip, \
         patch("app.services.session_service.end", new_callable=AsyncMock):
        mock_trip.return_value = None
        await add_expense.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_handle_input_empty_text_re_prompts():
    ctx = make_ctx(raw_text="   ")
    session = make_session("add_expense", STEP_ASK_EXPENSE)
    trip = make_trip()

    with _patch_trip() as mock_trip:
        mock_trip.return_value = trip
        await add_expense.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once()
    assert ctx.client.send_message.call_args[0][1] == messages.ASK_EXPENSE


async def test_handle_input_valid_text_creates_expense():
    ctx = make_ctx(raw_text="coffee 5", username="alice")
    session = make_session("add_expense", STEP_ASK_EXPENSE)
    trip = make_trip()
    exp = make_expense(name="coffee", amount="5.00")
    created = CreatedExpense(expense=exp, splits=[make_split("alice", "5.00")])

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members, \
         _patch_member_add(), \
         _patch_expense_add() as mock_add, \
         _patch_session_end():
        mock_trip.return_value = trip
        mock_members.return_value = ["alice"]
        mock_add.return_value = created
        await add_expense.handle_input(ctx, session)

    mock_add.assert_called_once()
    text = ctx.client.send_message.call_args[0][1]
    assert "coffee" in text


async def test_handle_input_invalid_format_sends_usage():
    ctx = make_ctx(raw_text="justnoprice", username="alice")
    session = make_session("add_expense", STEP_ASK_EXPENSE)
    trip = make_trip()

    with _patch_trip() as mock_trip, \
         _patch_member_usernames() as mock_members, \
         _patch_session_end():
        mock_trip.return_value = trip
        mock_members.return_value = ["alice"]
        await add_expense.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ADD_EXPENSE_USAGE)
