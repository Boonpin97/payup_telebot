"""Tests for webhook routing: command parsing and dispatch."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.commands.new_trip import STEP_ASK_NAME
from app.telegram import messages
from app.telegram.webhook import _parse_command, _route_command, handle_update

from .conftest import CHAT_ID, USER_A_ID, USER_A_NAME, make_client, make_ctx, make_session


# ---------------------------------------------------------------------------
# _parse_command — strips leading slash, @botname suffix, splits args
# ---------------------------------------------------------------------------


def test_parse_command_simple():
    assert _parse_command("/new_trip") == ("new_trip", "")


def test_parse_command_strips_botname_suffix():
    assert _parse_command("/new_trip@payup123_bot") == ("new_trip", "")


def test_parse_command_preserves_args():
    assert _parse_command("/add_expense pasta 10") == ("add_expense", "pasta 10")


def test_parse_command_args_with_botname():
    assert _parse_command("/add_expense@mybot pasta 10") == ("add_expense", "pasta 10")


def test_parse_command_no_args():
    name, args = _parse_command("/summary")
    assert name == "summary"
    assert args == ""


def test_parse_command_multi_word_args():
    name, args = _parse_command("/add_expense dinner at marina 50.00")
    assert name == "add_expense"
    assert args == "dinner at marina 50.00"


def test_parse_command_unknown_command_returns_name():
    name, args = _parse_command("/foobar")
    assert name == "foobar"
    assert args == ""


# ---------------------------------------------------------------------------
# _route_command — unknown command is silently ignored
# ---------------------------------------------------------------------------


async def test_route_unknown_command_does_nothing():
    ctx = make_ctx()
    await _route_command(ctx, "/unknowncmd")
    ctx.client.send_message.assert_not_called()


# ---------------------------------------------------------------------------
# /start and /help — send GREETING directly (no Firestore needed)
# ---------------------------------------------------------------------------


async def test_route_start_sends_greeting():
    ctx = make_ctx()
    await _route_command(ctx, "/start")
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.GREETING)


async def test_route_help_sends_greeting():
    ctx = make_ctx()
    await _route_command(ctx, "/help")
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.GREETING)


# ---------------------------------------------------------------------------
# /new_trip dispatch — mock session_service to avoid Firestore
# ---------------------------------------------------------------------------


async def test_route_new_trip_creates_session_and_prompts():
    ctx = make_ctx()
    with patch("app.services.session_service.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_session("new_trip", STEP_ASK_NAME)
        await _route_command(ctx, "/new_trip")
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ASK_TRIP_NAME)


async def test_route_botname_suffix_dispatches_correctly():
    """/new_trip@payup123_bot must route identically to /new_trip."""
    ctx = make_ctx()
    with patch("app.services.session_service.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = make_session("new_trip", STEP_ASK_NAME)
        await _route_command(ctx, "/new_trip@payup123_bot")
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.ASK_TRIP_NAME)


# ---------------------------------------------------------------------------
# /add_expense — args_text forwarded correctly
# ---------------------------------------------------------------------------


async def test_route_add_expense_sets_args_text_and_routes():
    """`args_text` on the context must reflect the inline arguments."""
    ctx = make_ctx()
    with patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock) as mock_trip:
        mock_trip.return_value = None
        await _route_command(ctx, "/add_expense pasta 10")
    assert ctx.args_text == "pasta 10"
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


# ---------------------------------------------------------------------------
# /summary — routes, respects no-active-trip path
# ---------------------------------------------------------------------------


async def test_route_summary_sends_no_active_trip_when_none():
    ctx = make_ctx()
    with patch("app.services.trip_service.get_active_trip", new_callable=AsyncMock) as mock_trip:
        mock_trip.return_value = None
        await _route_command(ctx, "/summary")
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.NO_ACTIVE_TRIP)


# ---------------------------------------------------------------------------
# handle_update — top-level dispatcher
# ---------------------------------------------------------------------------


def _make_message_update(text: str, user_id: int = USER_A_ID, username: str = USER_A_NAME):
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": CHAT_ID, "type": "group", "title": "Test"},
            "from": {"id": user_id, "username": username, "is_bot": False},
            "text": text,
        },
    }


async def test_handle_update_routes_new_trip():
    update = _make_message_update("/new_trip")
    with patch("app.telegram.webhook.get_telegram_client") as mock_factory, \
         patch("app.services.session_service.create", new_callable=AsyncMock) as mock_create:
        mock_factory.return_value = make_client()
        mock_create.return_value = make_session("new_trip", STEP_ASK_NAME)
        await handle_update(update)
    mock_create.assert_called_once()


async def test_handle_update_ignores_empty_update():
    await handle_update({"update_id": 99})


async def test_handle_update_non_command_text_calls_maybe_handle():
    update = _make_message_update("BKK")
    with patch("app.telegram.webhook.get_telegram_client") as mock_factory, \
         patch("app.commands.inputs.maybe_handle", new_callable=AsyncMock) as mock_h:
        mock_factory.return_value = make_client()
        await handle_update(update)
    mock_h.assert_called_once()


async def test_handle_update_ignores_new_chat_members_message():
    update = {
        "update_id": 2,
        "message": {
            "message_id": 2,
            "date": 1700000000,
            "chat": {"id": CHAT_ID, "type": "group"},
            "from": {"id": USER_A_ID, "username": USER_A_NAME},
            "new_chat_members": [{"id": 99, "username": "newguy"}],
            "text": "",
        },
    }
    with patch("app.telegram.webhook.get_telegram_client") as mock_factory:
        mock_factory.return_value = make_client()
        await handle_update(update)
    # No crash, no message sent
