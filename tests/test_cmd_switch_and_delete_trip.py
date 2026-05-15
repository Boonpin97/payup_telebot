"""Tests for /switch_trip and /delete_trip commands."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.commands import delete_trip, switch_trip
from app.telegram import keyboards, messages

from .conftest import CHAT_ID, make_ctx, make_trip


def _patch_list_trips():
    return patch("app.services.trip_service.list_trips", new_callable=AsyncMock)


# ---------------------------------------------------------------------------
# /switch_trip
# ---------------------------------------------------------------------------


async def test_switch_trip_no_trips_sends_empty_list_message():
    ctx = make_ctx()
    with _patch_list_trips() as mock_list:
        mock_list.return_value = []
        await switch_trip.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.EMPTY_TRIP_LIST)


async def test_switch_trip_one_trip_sends_picker():
    ctx = make_ctx()
    with _patch_list_trips() as mock_list:
        mock_list.return_value = [make_trip(trip_id="t1", trip_name="BKK")]
        await switch_trip.handle(ctx)

    ctx.client.send_message.assert_called_once()
    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    all_data = [btn["callback_data"] for row in keyboard["inline_keyboard"] for btn in row]
    assert any(d.startswith(keyboards.SWITCH_TRIP_PICK) for d in all_data)


async def test_switch_trip_multiple_trips_shows_all():
    ctx = make_ctx()
    trips = [
        make_trip(trip_id="t1", trip_name="BKK"),
        make_trip(trip_id="t2", trip_name="Japan"),
        make_trip(trip_id="t3", trip_name="Europe"),
    ]
    with _patch_list_trips() as mock_list:
        mock_list.return_value = trips
        await switch_trip.handle(ctx)

    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    labels = [btn["text"] for row in keyboard["inline_keyboard"] for btn in row]
    assert "BKK" in labels
    assert "Japan" in labels
    assert "Europe" in labels


async def test_switch_trip_keyboard_embeds_trip_ids():
    ctx = make_ctx()
    with _patch_list_trips() as mock_list:
        mock_list.return_value = [make_trip(trip_id="xyz123", trip_name="Trip")]
        await switch_trip.handle(ctx)

    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    all_data = [btn["callback_data"] for row in keyboard["inline_keyboard"] for btn in row]
    assert any("xyz123" in d for d in all_data)


# ---------------------------------------------------------------------------
# /delete_trip
# ---------------------------------------------------------------------------


async def test_delete_trip_no_trips_sends_empty_list_message():
    ctx = make_ctx()
    with _patch_list_trips() as mock_list:
        mock_list.return_value = []
        await delete_trip.handle(ctx)
    ctx.client.send_message.assert_called_once_with(CHAT_ID, messages.EMPTY_TRIP_LIST)


async def test_delete_trip_one_trip_sends_picker():
    ctx = make_ctx()
    with _patch_list_trips() as mock_list:
        mock_list.return_value = [make_trip(trip_id="t1", trip_name="BKK")]
        await delete_trip.handle(ctx)

    ctx.client.send_message.assert_called_once()
    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    all_data = [btn["callback_data"] for row in keyboard["inline_keyboard"] for btn in row]
    assert any(d.startswith(keyboards.DELETE_TRIP_PICK) for d in all_data)


async def test_delete_trip_multiple_trips_shows_all():
    ctx = make_ctx()
    trips = [
        make_trip(trip_id="t1", trip_name="BKK"),
        make_trip(trip_id="t2", trip_name="Japan"),
    ]
    with _patch_list_trips() as mock_list:
        mock_list.return_value = trips
        await delete_trip.handle(ctx)

    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    labels = [btn["text"] for row in keyboard["inline_keyboard"] for btn in row]
    assert "BKK" in labels
    assert "Japan" in labels


async def test_delete_trip_uses_deltrip_not_switch_action():
    """delete_trip picker must use DELETE_TRIP_PICK, not SWITCH_TRIP_PICK."""
    ctx = make_ctx()
    with _patch_list_trips() as mock_list:
        mock_list.return_value = [make_trip()]
        await delete_trip.handle(ctx)

    keyboard = ctx.client.send_message.call_args[1]["reply_markup"]
    all_data = [btn["callback_data"] for row in keyboard["inline_keyboard"] for btn in row]
    assert not any(d.startswith(keyboards.SWITCH_TRIP_PICK) for d in all_data)
    assert any(d.startswith(keyboards.DELETE_TRIP_PICK) for d in all_data)
