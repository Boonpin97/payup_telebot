"""Test configuration and shared helpers."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

# Make ``import app`` work without installing the package.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Avoid loading any real .env in tests.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("ENVIRONMENT", "test")

from app.commands.context import CallbackContext, CommandContext
from app.models.expense import Expense
from app.models.member import Member
from app.models.session import Session
from app.models.split import ExpenseSplit
from app.models.trip import Trip

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

CHAT_ID = 100
USER_A_ID = 1
USER_A_NAME = "alice"
USER_B_ID = 2
USER_B_NAME = "bob"
TRIP_ID = "trip-001"
TRIP_NAME = "BKK Trip"
GROUP_ID = f"chat_{CHAT_ID}"
EXPENSE_ID = "exp-001"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_client() -> MagicMock:
    client = MagicMock()
    client.send_message = AsyncMock(return_value={"message_id": 42})
    client.answer_callback_query = AsyncMock(return_value=None)
    client.edit_message_reply_markup = AsyncMock(return_value=None)
    return client


def make_ctx(
    *,
    chat_id: int = CHAT_ID,
    user_id: Optional[int] = USER_A_ID,
    username: str = USER_A_NAME,
    args_text: str = "",
    raw_text: str = "",
    message_id: int = 1,
) -> CommandContext:
    return CommandContext(
        chat_id=chat_id,
        chat_title="Test Group",
        user_id=user_id,
        username=username,
        message_id=message_id,
        raw_text=raw_text,
        args_text=args_text,
        client=make_client(),
    )


def make_callback_ctx(
    *,
    chat_id: int = CHAT_ID,
    user_id: Optional[int] = USER_A_ID,
    username: str = USER_A_NAME,
    message_id: int = 10,
    callback_query_id: str = "cq-1",
    data: str = "",
) -> CallbackContext:
    return CallbackContext(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        message_id=message_id,
        callback_query_id=callback_query_id,
        data=data,
        client=make_client(),
    )


def make_session(
    command_name: str,
    step: str,
    payload: Optional[dict] = None,
    user_id: int = USER_A_ID,
    chat_id: int = CHAT_ID,
) -> Session:
    return Session(
        session_id=f"chat:{chat_id}:user:{user_id}:input",
        group_id=GROUP_ID,
        chat_id=chat_id,
        user_id=user_id,
        command_name=command_name,
        step=step,
        payload=payload or {},
        expires_at=datetime.now(tz=timezone.utc) + timedelta(seconds=300),
    )


def make_trip(
    trip_id: str = TRIP_ID,
    trip_name: str = TRIP_NAME,
    chat_id: int = CHAT_ID,
) -> Trip:
    return Trip(
        trip_id=trip_id,
        group_id=f"chat_{chat_id}",
        trip_name=trip_name,
    )


def make_expense(
    expense_id: str = EXPENSE_ID,
    name: str = "pasta",
    amount: str = "10.00",
    payer: str = USER_A_NAME,
    trip_id: str = TRIP_ID,
    participants: Optional[list[str]] = None,
) -> Expense:
    parts = participants if participants is not None else [payer]
    return Expense(
        expense_id=expense_id,
        trip_id=trip_id,
        group_id=GROUP_ID,
        expense_name=name,
        amount=Decimal(amount),
        paid_by_username=payer,
        participant_usernames=parts,
        created_by_username=payer,
    )


def make_split(username: str, amount: str = "5.00", expense_id: str = EXPENSE_ID) -> ExpenseSplit:
    return ExpenseSplit(
        split_id=username,
        expense_id=expense_id,
        username=username,
        amount_owed=Decimal(amount),
    )


def make_member(username: str, user_id: Optional[int] = None) -> Member:
    return Member(
        member_id=username,
        username=username,
        telegram_user_id=user_id,
    )
