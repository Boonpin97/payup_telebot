"""Tests for the usability commands: /cancel, /members, /trips, /expenses,
/edit_expense (and its picker callback).

These tests use fake in-memory stand-ins for repositories and services so
the handlers can run without touching Firestore or Telegram.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

import pytest

from app.commands import (
    cancel,
    callbacks,
    edit_expense,
    expenses_view,
    inputs,
    members_view,
    new_trip,
    trips_view,
)
from app.commands.context import CallbackContext, CommandContext
from app.models.expense import Expense
from app.models.trip import Trip
from app.telegram import keyboards
from app.utils.timeouts import utcnow


# --- fakes ---------------------------------------------------------------


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.callback_answers: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: Optional[dict] = None,
        parse_mode: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        disable_web_page_preview: Optional[bool] = True,
    ) -> dict:
        self.sent.append(
            {"chat_id": chat_id, "text": text, "reply_markup": reply_markup, "parse_mode": parse_mode}
        )
        return {}

    async def answer_callback_query(
        self, callback_query_id: str, *, text: Optional[str] = None, show_alert: bool = False
    ) -> dict:
        self.callback_answers.append(
            {"id": callback_query_id, "text": text, "show_alert": show_alert}
        )
        return {}

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: Optional[dict] = None,
        parse_mode: Optional[str] = None,
    ) -> dict:
        self.edits.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": reply_markup,
                "parse_mode": parse_mode,
            }
        )
        return {}

    async def edit_message_reply_markup(
        self, chat_id: int, message_id: int, *, reply_markup: Optional[dict] = None
    ) -> dict:
        self.edits.append({"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup})
        return {}


def _make_ctx(client: FakeTelegramClient, *, chat_id: int = 1, raw_text: str = "") -> CommandContext:
    return CommandContext(
        chat_id=chat_id,
        chat_title=None,
        user_id=42,
        username="tester",
        message_id=None,
        raw_text=raw_text,
        args_text="",
        client=client,  # type: ignore[arg-type]
    )


def _make_callback_ctx(
    client: FakeTelegramClient, *, chat_id: int = 1, data: str = ""
) -> CallbackContext:
    return CallbackContext(
        chat_id=chat_id,
        user_id=42,
        username="tester",
        message_id=99,
        callback_query_id="cq1",
        data=data,
        client=client,  # type: ignore[arg-type]
    )


def _trip(name: str = "Bangkok 2026", trip_id: str = "t1") -> Trip:
    return Trip(trip_id=trip_id, group_id="g:1", trip_name=name)


def _expense(name: str, amount: str, *, expense_id: str = None, payer: str = "tester") -> Expense:
    return Expense(
        expense_id=expense_id or f"exp_{name}",
        trip_id="t1",
        group_id="g:1",
        expense_name=name,
        amount=Decimal(amount),
        paid_by_username=payer,
        created_by_username=payer,
    )


# --- /cancel -------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_ends_active_session_and_replies(monkeypatch):
    from app.commands import sessions

    started: dict[str, Any] = {}

    async def fake_get_alive(chat_id):
        return started.get("session")

    async def fake_end(chat_id):
        started.pop("session", None)

    started["session"] = type("S", (), {"step": "ask_name"})()
    monkeypatch.setattr(sessions, "get_alive_input", fake_get_alive)
    monkeypatch.setattr(sessions, "end_input", fake_end)

    client = FakeTelegramClient()
    await cancel.handle(_make_ctx(client))

    assert "session" not in started
    assert client.sent[-1]["text"] == "Cancelled."


@pytest.mark.asyncio
async def test_cancel_with_no_session_replies_nothing_to_cancel(monkeypatch):
    from app.commands import sessions

    async def fake_get_alive(chat_id):
        return None

    monkeypatch.setattr(sessions, "get_alive_input", fake_get_alive)

    client = FakeTelegramClient()
    await cancel.handle(_make_ctx(client))

    assert client.sent[-1]["text"] == "There is no active action to cancel."


@pytest.mark.asyncio
async def test_cancelled_session_not_consumed_by_inputs_maybe_handle(monkeypatch):
    from app.commands import sessions

    async def fake_get_alive(chat_id, user_id):
        return None, False  # session has been ended

    monkeypatch.setattr(sessions, "get_alive_input", fake_get_alive)

    client = FakeTelegramClient()
    consumed = await inputs.maybe_handle(_make_ctx(client, raw_text="some text"))
    assert consumed is False
    assert client.sent == []


# --- /members ------------------------------------------------------------


@pytest.mark.asyncio
async def test_members_no_active_trip_uses_no_active_trip_message(monkeypatch):
    async def fake_get(chat_id):
        return None

    monkeypatch.setattr(members_view.trip_service, "get_active_trip", fake_get)

    client = FakeTelegramClient()
    await members_view.handle(_make_ctx(client))
    assert "No active trip" in client.sent[-1]["text"]


@pytest.mark.asyncio
async def test_members_empty_list_renders_none(monkeypatch):
    async def fake_trip(chat_id):
        return _trip("Bangkok 2026")

    async def fake_active_usernames(chat_id, trip_id):
        return []

    monkeypatch.setattr(members_view.trip_service, "get_active_trip", fake_trip)
    monkeypatch.setattr(members_view.member_service, "active_usernames", fake_active_usernames)

    client = FakeTelegramClient()
    await members_view.handle(_make_ctx(client))
    text = client.sent[-1]["text"]
    assert "Bangkok 2026" in text
    assert "(none)" in text


@pytest.mark.asyncio
async def test_members_populated_list_renders_each_username(monkeypatch):
    async def fake_trip(chat_id):
        return _trip("Bangkok 2026")

    async def fake_active_usernames(chat_id, trip_id):
        return ["alice", "bob"]

    monkeypatch.setattr(members_view.trip_service, "get_active_trip", fake_trip)
    monkeypatch.setattr(members_view.member_service, "active_usernames", fake_active_usernames)

    client = FakeTelegramClient()
    await members_view.handle(_make_ctx(client))
    text = client.sent[-1]["text"]
    assert "@alice" in text and "@bob" in text


# --- /trips --------------------------------------------------------------


@pytest.mark.asyncio
async def test_trips_with_none_uses_empty_trip_list_message(monkeypatch):
    async def fake_list(chat_id):
        return []

    monkeypatch.setattr(trips_view.trip_service, "list_trips", fake_list)

    client = FakeTelegramClient()
    await trips_view.handle(_make_ctx(client))
    assert "No trips" in client.sent[-1]["text"]


@pytest.mark.asyncio
async def test_trips_marks_active_trip(monkeypatch):
    trips = [_trip("Bangkok 2026", "t1"), _trip("Tokyo 2027", "t2")]

    async def fake_list(chat_id):
        return trips

    class FakeGroup:
        active_trip_id = "t2"

    async def fake_group_get(chat_id):
        return FakeGroup()

    monkeypatch.setattr(trips_view.trip_service, "list_trips", fake_list)
    monkeypatch.setattr(trips_view.group_repository, "get", fake_group_get)

    client = FakeTelegramClient()
    await trips_view.handle(_make_ctx(client))
    text = client.sent[-1]["text"]
    assert "Bangkok 2026" in text
    assert "Tokyo 2027 (active)" in text
    assert "Bangkok 2026 (active)" not in text


# --- /expenses -----------------------------------------------------------


@pytest.mark.asyncio
async def test_expenses_no_active_trip(monkeypatch):
    async def fake_trip(chat_id):
        return None

    monkeypatch.setattr(expenses_view.trip_service, "get_active_trip", fake_trip)

    client = FakeTelegramClient()
    await expenses_view.handle(_make_ctx(client))
    assert "No active trip" in client.sent[-1]["text"]


@pytest.mark.asyncio
async def test_expenses_empty_returns_empty_state(monkeypatch):
    async def fake_trip(chat_id):
        return _trip()

    async def fake_list(chat_id, trip_id):
        return []

    monkeypatch.setattr(expenses_view.trip_service, "get_active_trip", fake_trip)
    monkeypatch.setattr(expenses_view.expense_repository, "list_active", fake_list)

    client = FakeTelegramClient()
    await expenses_view.handle(_make_ctx(client))
    assert client.sent[-1]["text"] == "No expenses recorded in this trip yet."


@pytest.mark.asyncio
async def test_expenses_limits_to_ten_and_shows_remaining(monkeypatch):
    base = utcnow()
    expenses = [
        Expense(
            expense_id=f"exp_{i:02d}",
            trip_id="t1",
            group_id="g:1",
            expense_name=f"item-{i}",
            amount=Decimal("1.00"),
            paid_by_username="tester",
            created_by_username="tester",
            created_at=base + timedelta(seconds=i),
        )
        for i in range(15)
    ]

    async def fake_trip(chat_id):
        return _trip()

    async def fake_list(chat_id, trip_id):
        return expenses

    monkeypatch.setattr(expenses_view.trip_service, "get_active_trip", fake_trip)
    monkeypatch.setattr(expenses_view.expense_repository, "list_active", fake_list)

    client = FakeTelegramClient()
    await expenses_view.handle(_make_ctx(client))
    text = client.sent[-1]["text"]
    # Newest items first, oldest 5 not shown.
    assert "item-14" in text
    assert "item-5" in text
    assert "item-4" not in text
    assert "...and 5 more" in text


# --- /edit_expense + picker callback ------------------------------------


@pytest.mark.asyncio
async def test_edit_expense_no_active_trip(monkeypatch):
    async def fake_trip(chat_id):
        return None

    monkeypatch.setattr(edit_expense.trip_service, "get_active_trip", fake_trip)

    client = FakeTelegramClient()
    await edit_expense.handle(_make_ctx(client))
    assert "No active trip" in client.sent[-1]["text"]
    assert client.sent[-1]["reply_markup"] is None


@pytest.mark.asyncio
async def test_edit_expense_no_expenses(monkeypatch):
    async def fake_trip(chat_id):
        return _trip()

    async def fake_list(chat_id, trip_id):
        return []

    monkeypatch.setattr(edit_expense.trip_service, "get_active_trip", fake_trip)
    monkeypatch.setattr(edit_expense.expense_repository, "list_active", fake_list)

    client = FakeTelegramClient()
    await edit_expense.handle(_make_ctx(client))
    assert client.sent[-1]["text"] == "No expenses recorded in this trip yet."


@pytest.mark.asyncio
async def test_edit_expense_shows_vertical_picker(monkeypatch):
    async def fake_trip(chat_id):
        return _trip()

    async def fake_list(chat_id, trip_id):
        return [_expense("pasta", "10.00", expense_id="exp_p")]

    monkeypatch.setattr(edit_expense.trip_service, "get_active_trip", fake_trip)
    monkeypatch.setattr(edit_expense.expense_repository, "list_active", fake_list)

    client = FakeTelegramClient()
    await edit_expense.handle(_make_ctx(client))
    sent = client.sent[-1]
    assert sent["text"] == "Select an expense to edit:"
    rows = sent["reply_markup"]["inline_keyboard"]
    # Vertical: one row per expense.
    assert len(rows) == 1
    button = rows[0][0]
    assert button["callback_data"] == f"{keyboards.EDIT_EXPENSE_PICK}:exp_p"
    assert "pasta" in button["text"]


@pytest.mark.asyncio
async def test_edit_expense_pick_opens_edit_menu(monkeypatch):
    async def fake_trip(chat_id):
        return _trip()

    async def fake_get(chat_id, trip_id, expense_id):
        return _expense("pasta", "10.00", expense_id=expense_id)

    monkeypatch.setattr(callbacks.trip_service, "get_active_trip", fake_trip)
    monkeypatch.setattr(callbacks.expense_repository, "get", fake_get)

    client = FakeTelegramClient()
    ctx = _make_callback_ctx(client, data=f"{keyboards.EDIT_EXPENSE_PICK}:exp_p")
    # Use a fresh "now" so the expiry check passes.
    await callbacks.handle(ctx, int(utcnow().timestamp()))

    assert client.edits, "expected picker message to be edited in place"
    edit_menu_msg = client.edits[-1]
    assert edit_menu_msg["text"] == "What else would you like to edit?"
    rows = edit_menu_msg["reply_markup"]["inline_keyboard"]
    # Existing edit menu has Name / Amount / People / Split Type / Done.
    flat = [b["text"] for row in rows for b in row]
    assert "Name" in flat and "Amount" in flat and "People" in flat and "Done" in flat


@pytest.mark.asyncio
async def test_edit_expense_pick_expired_message_uses_existing_expiry(monkeypatch):
    client = FakeTelegramClient()
    ctx = _make_callback_ctx(client, data=f"{keyboards.EDIT_EXPENSE_PICK}:exp_p")
    # Force expiry: pretend the original message is 400s old (>180s threshold).
    expired_unix = int((utcnow() - timedelta(seconds=400)).timestamp())
    await callbacks.handle(ctx, expired_unix)

    # The expiry path answers the callback with SESSION_EXPIRED alert.
    assert client.callback_answers, "expected callback answer for expiry"
    last = client.callback_answers[-1]
    assert last["show_alert"] is True
    assert "expired" in (last["text"] or "").lower()
    # No edit menu opened.
    assert all(e.get("text") != "What else would you like to edit?" for e in client.edits)


# --- /new_trip session is cancelled by /cancel ---------------------------


@pytest.mark.asyncio
async def test_new_trip_session_can_be_cancelled(monkeypatch):
    """End-to-end: starting /new_trip creates a session, /cancel ends it."""
    from app.commands import sessions

    fake_store: dict[int, Any] = {}

    async def fake_start(*, chat_id, command_name, step, payload=None, user_id=None, callback_message_id=None):
        sess = type("S", (), {"step": step, "payload": payload or {}})()
        fake_store[chat_id] = sess
        return sess

    async def fake_get_alive(chat_id):
        return fake_store.get(chat_id)

    async def fake_end(chat_id):
        fake_store.pop(chat_id, None)

    monkeypatch.setattr(sessions, "start_input", fake_start)
    monkeypatch.setattr(sessions, "get_alive_input", fake_get_alive)
    monkeypatch.setattr(sessions, "end_input", fake_end)

    client = FakeTelegramClient()
    # Start /new_trip → creates an ask_name session.
    await new_trip.handle(_make_ctx(client))
    assert fake_store[1].step == new_trip.STEP_ASK_NAME

    # /cancel ends it.
    await cancel.handle(_make_ctx(client))
    assert 1 not in fake_store
    assert client.sent[-1]["text"] == "Cancelled."
