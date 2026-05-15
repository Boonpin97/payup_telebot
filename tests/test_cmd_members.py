"""Tests for /add_members and /delete_members commands."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.commands import members
from app.commands.members import STEP_ASK_ADD_USERNAMES, STEP_ASK_DELETE_USERNAMES
from app.services.member_service import AddMembersResult, RemoveMembersResult
from app.telegram import messages

from .conftest import CHAT_ID, TRIP_ID, USER_A_ID, make_ctx, make_session, make_trip


def _patch_trip():
    return patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock)


def _patch_add_members():
    return patch("app.services.member_service.add_members", new_callable=AsyncMock)


def _patch_remove_members():
    return patch("app.services.member_service.remove_members", new_callable=AsyncMock)


def _patch_session_create():
    return patch("app.services.session_service.create", new_callable=AsyncMock)


def _patch_session_end():
    return patch("app.services.session_service.end", new_callable=AsyncMock)


def _add_result(added=None, already=None, current=None) -> AddMembersResult:
    return AddMembersResult(
        added=added or [],
        already_present=already or [],
        current_members=current or [],
    )


def _remove_result(removed=None, not_in=None, current=None) -> RemoveMembersResult:
    return RemoveMembersResult(
        removed=removed or [],
        not_in_trip=not_in or [],
        current_members=current or [],
    )


# ---------------------------------------------------------------------------
# /add_members
# ---------------------------------------------------------------------------


async def test_add_no_active_trip_sends_no_active_trip():
    ctx = make_ctx(args_text="@bob")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await members.add(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_add_with_inline_args_calls_add_members():
    ctx = make_ctx(args_text="@bob @charlie")
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_add_members() as mock_add:
        mock_trip.return_value = trip
        mock_add.return_value = _add_result(added=["bob", "charlie"], current=["bob", "charlie"])
        await members.add(ctx)

    mock_add.assert_called_once_with(CHAT_ID, TRIP_ID, ["bob", "charlie"])


async def test_add_with_inline_args_sends_confirmation():
    ctx = make_ctx(args_text="@bob")
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_add_members() as mock_add:
        mock_trip.return_value = trip
        mock_add.return_value = _add_result(added=["bob"], current=["bob"])
        await members.add(ctx)

    ctx.client.send_message.assert_called_once()
    assert "bob" in ctx.client.send_message.call_args[0][1]


async def test_add_already_present_member_shows_already_in_trip():
    ctx = make_ctx(args_text="@bob")
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_add_members() as mock_add:
        mock_trip.return_value = trip
        mock_add.return_value = _add_result(already=["bob"], current=["bob"])
        await members.add(ctx)

    text = ctx.client.send_message.call_args[0][1]
    assert "already" in text.lower()


async def test_add_no_args_no_trip_sends_no_active_trip():
    ctx = make_ctx(args_text="")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await members.add(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_add_no_args_starts_prompt():
    ctx = make_ctx(args_text="")
    trip = make_trip()
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("add_members", STEP_ASK_ADD_USERNAMES)

    with _patch_trip() as mock_trip, \
         patch("app.services.session_service.create", side_effect=capture):
        mock_trip.return_value = trip
        await members.add(ctx)

    assert captured[0]["step"] == STEP_ASK_ADD_USERNAMES


async def test_add_handle_input_empty_text_re_prompts():
    ctx = make_ctx(raw_text="")
    session = make_session("add_members", STEP_ASK_ADD_USERNAMES)
    await members.handle_input(ctx, session)
    ctx.client.send_message.assert_called_once()
    assert "@" in ctx.client.send_message.call_args[0][1]  # shows example


async def test_add_handle_input_no_trip_ends_session():
    ctx = make_ctx(raw_text="@bob")
    session = make_session("add_members", STEP_ASK_ADD_USERNAMES)

    with _patch_trip() as mock_trip, _patch_session_end():
        mock_trip.return_value = None
        await members.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_add_handle_input_valid_adds_members():
    ctx = make_ctx(raw_text="@bob @charlie")
    session = make_session("add_members", STEP_ASK_ADD_USERNAMES)
    trip = make_trip()

    with _patch_trip() as mock_trip, \
         _patch_add_members() as mock_add, \
         _patch_session_end():
        mock_trip.return_value = trip
        mock_add.return_value = _add_result(added=["bob", "charlie"], current=["bob", "charlie"])
        await members.handle_input(ctx, session)

    mock_add.assert_called_once_with(CHAT_ID, TRIP_ID, ["bob", "charlie"])


# ---------------------------------------------------------------------------
# /delete_members
# ---------------------------------------------------------------------------


async def test_delete_no_active_trip_sends_no_active_trip():
    ctx = make_ctx(args_text="@bob")
    with _patch_trip() as mock_trip:
        mock_trip.return_value = None
        await members.delete(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


async def test_delete_with_inline_args_removes_members():
    ctx = make_ctx(args_text="@bob")
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_remove_members() as mock_remove:
        mock_trip.return_value = trip
        mock_remove.return_value = _remove_result(removed=["bob"], current=[])
        await members.delete(ctx)

    mock_remove.assert_called_once_with(CHAT_ID, TRIP_ID, ["bob"])


async def test_delete_member_not_in_trip_shows_not_in_trip():
    ctx = make_ctx(args_text="@ghost")
    trip = make_trip()

    with _patch_trip() as mock_trip, _patch_remove_members() as mock_remove:
        mock_trip.return_value = trip
        mock_remove.return_value = _remove_result(not_in=["ghost"], current=["alice"])
        await members.delete(ctx)

    text = ctx.client.send_message.call_args[0][1]
    assert "ghost" in text


async def test_delete_no_args_starts_prompt():
    ctx = make_ctx(args_text="")
    trip = make_trip()
    captured: list[dict] = []

    async def capture(**kwargs):
        captured.append(kwargs)
        return make_session("delete_members", STEP_ASK_DELETE_USERNAMES)

    with _patch_trip() as mock_trip, \
         patch("app.services.session_service.create", side_effect=capture):
        mock_trip.return_value = trip
        await members.delete(ctx)

    assert captured[0]["step"] == STEP_ASK_DELETE_USERNAMES


async def test_delete_handle_input_empty_text_re_prompts():
    ctx = make_ctx(raw_text="")
    session = make_session("delete_members", STEP_ASK_DELETE_USERNAMES)
    await members.handle_input(ctx, session)
    ctx.client.send_message.assert_called_once()
    assert "@" in ctx.client.send_message.call_args[0][1]


async def test_delete_handle_input_valid_removes_members():
    ctx = make_ctx(raw_text="@bob")
    session = make_session("delete_members", STEP_ASK_DELETE_USERNAMES)
    trip = make_trip()

    with _patch_trip() as mock_trip, \
         _patch_remove_members() as mock_remove, \
         _patch_session_end():
        mock_trip.return_value = trip
        mock_remove.return_value = _remove_result(removed=["bob"], current=[])
        await members.handle_input(ctx, session)

    mock_remove.assert_called_once_with(CHAT_ID, TRIP_ID, ["bob"])


async def test_delete_handle_input_no_trip_ends_session():
    ctx = make_ctx(raw_text="@bob")
    session = make_session("delete_members", STEP_ASK_DELETE_USERNAMES)

    with _patch_trip() as mock_trip, _patch_session_end():
        mock_trip.return_value = None
        await members.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)
