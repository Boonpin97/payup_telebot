"""Tests for the /new_trip command (two-step flow)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.commands import new_trip
from app.commands.new_trip import STEP_ASK_MEMBERS, STEP_ASK_NAME
from app.telegram import messages

from .conftest import (
    CHAT_ID,
    TRIP_ID,
    TRIP_NAME,
    USER_A_ID,
    USER_B_ID,
    USER_B_NAME,
    make_ctx,
    make_session,
    make_trip,
)


def _patch_create():
    return patch("app.services.session_service.create", new_callable=AsyncMock)


def _patch_end():
    return patch("app.services.session_service.end", new_callable=AsyncMock)


def _patch_trip_create():
    return patch("app.services.trip_service.create_trip", new_callable=AsyncMock)


# ---------------------------------------------------------------------------
# handle() — step 1: receive /new_trip, store session, ask for trip name
# ---------------------------------------------------------------------------


async def test_handle_sends_ask_trip_name():
    ctx = make_ctx()
    with _patch_create() as mock_create:
        mock_create.return_value = make_session("new_trip", STEP_ASK_NAME)
        await new_trip.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ASK_TRIP_NAME)


async def test_handle_session_keyed_to_invoking_user():
    """Session ID must embed the user who sent /new_trip so only they can answer."""
    ctx = make_ctx(user_id=USER_A_ID)
    captured: list[str] = []

    async def capture(**kwargs):
        captured.append(kwargs["session_id"])
        return make_session("new_trip", STEP_ASK_NAME)

    with patch("app.services.session_service.create", side_effect=capture):
        await new_trip.handle(ctx)

    assert captured, "session_service.create was never called"
    assert f"user:{USER_A_ID}" in captured[0]


async def test_handle_different_user_gets_separate_session_key():
    user_a_ids, user_b_ids = [], []

    async def capture(**kwargs):
        return make_session("new_trip", STEP_ASK_NAME, user_id=kwargs.get("user_id", 0))

    with patch("app.services.session_service.create", side_effect=capture):
        ctx_a = make_ctx(user_id=USER_A_ID)
        await new_trip.handle(ctx_a)
        ctx_b = make_ctx(user_id=USER_B_ID, username=USER_B_NAME)
        await new_trip.handle(ctx_b)

    # Both calls complete independently — no cross-user interference


# ---------------------------------------------------------------------------
# handle_input() — step 2: trip name reply
# ---------------------------------------------------------------------------


async def test_handle_input_name_step_prompts_for_members():
    ctx = make_ctx(raw_text="Summer Trip")
    session = make_session("new_trip", STEP_ASK_NAME)

    with _patch_create() as mock_create:
        mock_create.return_value = make_session("new_trip", STEP_ASK_MEMBERS)
        await new_trip.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once()
    assert ctx.client.send_message.call_args[0][1] == messages.ASK_TRIP_MEMBERS


async def test_handle_input_name_step_empty_text_re_prompts():
    ctx = make_ctx(raw_text="   ")
    session = make_session("new_trip", STEP_ASK_NAME)

    with _patch_create():
        await new_trip.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ASK_TRIP_NAME)


async def test_handle_input_name_step_whitespace_only_re_prompts():
    ctx = make_ctx(raw_text="\t\n")
    session = make_session("new_trip", STEP_ASK_NAME)

    with _patch_create():
        await new_trip.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ASK_TRIP_NAME)


async def test_handle_input_name_step_stores_trip_name_in_payload():
    ctx = make_ctx(raw_text="Japan 2026")
    session = make_session("new_trip", STEP_ASK_NAME)
    captured: dict = {}

    async def capture(**kwargs):
        captured.update(kwargs)
        return make_session("new_trip", STEP_ASK_MEMBERS, payload=kwargs.get("payload"))

    with patch("app.services.session_service.create", side_effect=capture):
        await new_trip.handle_input(ctx, session)

    assert captured.get("payload", {}).get("trip_name") == "Japan 2026"


# ---------------------------------------------------------------------------
# handle_input() — step 3: members reply
# ---------------------------------------------------------------------------


async def test_handle_input_members_step_creates_trip_with_parsed_usernames():
    ctx = make_ctx(raw_text="@bob @charlie")
    session = make_session("new_trip", STEP_ASK_MEMBERS, payload={"trip_name": "Beach"})
    trip = make_trip(trip_name="Beach")

    with _patch_end(), _patch_trip_create() as mock_create:
        mock_create.return_value = trip
        await new_trip.handle_input(ctx, session)

    mock_create.assert_called_once()
    kw = mock_create.call_args[1]
    assert kw["trip_name"] == "Beach"
    assert sorted(kw["member_usernames"]) == ["bob", "charlie"]


async def test_handle_input_members_step_bare_at_creates_trip_with_no_members():
    """A bare '@' is not a valid username → parse_usernames returns [] → trip created empty."""
    ctx = make_ctx(raw_text="@")
    session = make_session("new_trip", STEP_ASK_MEMBERS, payload={"trip_name": "Solo"})
    trip = make_trip(trip_name="Solo")

    with _patch_end(), _patch_trip_create() as mock_create:
        mock_create.return_value = trip
        await new_trip.handle_input(ctx, session)

    assert mock_create.call_args[1]["member_usernames"] == []


async def test_handle_input_members_step_empty_text_re_prompts_for_name():
    """Empty text in any step re-prompts for the trip name (existing guard in handle_input)."""
    ctx = make_ctx(raw_text="")
    session = make_session("new_trip", STEP_ASK_MEMBERS, payload={"trip_name": "Solo"})

    with _patch_create():
        await new_trip.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ASK_TRIP_NAME)


async def test_handle_input_members_step_sends_confirmation_with_trip_name():
    ctx = make_ctx(raw_text="@alice")
    session = make_session("new_trip", STEP_ASK_MEMBERS, payload={"trip_name": "Bali"})
    trip = make_trip(trip_name="Bali")

    with _patch_end(), _patch_trip_create() as mock_create:
        mock_create.return_value = trip
        await new_trip.handle_input(ctx, session)

    ctx.client.send_message.assert_called_once()
    text = ctx.client.send_message.call_args[0][1]
    assert "Bali" in text


async def test_handle_input_members_step_missing_payload_falls_back_to_untitled():
    ctx = make_ctx(raw_text="@alice")
    session = make_session("new_trip", STEP_ASK_MEMBERS, payload={})
    trip = make_trip(trip_name="Untitled trip")

    with _patch_end(), _patch_trip_create() as mock_create:
        mock_create.return_value = trip
        await new_trip.handle_input(ctx, session)

    assert mock_create.call_args[1]["trip_name"] == "Untitled trip"


async def test_handle_input_members_step_deduplicates_usernames():
    ctx = make_ctx(raw_text="@alice @alice @bob")
    session = make_session("new_trip", STEP_ASK_MEMBERS, payload={"trip_name": "T"})
    trip = make_trip()

    with _patch_end(), _patch_trip_create() as mock_create:
        mock_create.return_value = trip
        await new_trip.handle_input(ctx, session)

    usernames = mock_create.call_args[1]["member_usernames"]
    assert usernames.count("alice") == 1


async def test_handle_input_members_step_passes_creator_info():
    ctx = make_ctx(user_id=USER_A_ID, username="alice", raw_text="@bob")
    session = make_session("new_trip", STEP_ASK_MEMBERS, payload={"trip_name": "Trip"})
    trip = make_trip()

    with _patch_end(), _patch_trip_create() as mock_create:
        mock_create.return_value = trip
        await new_trip.handle_input(ctx, session)

    kw = mock_create.call_args[1]
    assert kw["created_by_user_id"] == USER_A_ID
    assert kw["created_by_username"] == "alice"
