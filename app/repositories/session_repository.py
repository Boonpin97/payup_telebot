"""Session state repository.

Sessions are short-lived multi-step interaction state (asking for an expense
name, capturing a custom split, etc.).  Each one carries an ``expires_at``
timestamp so stale interactions are rejected.
"""
from __future__ import annotations

from typing import Optional

from ..models.session import Session
from ..utils.timeouts import utcnow
from .firestore_client import get_firestore, run_in_thread


def _doc(session_id: str):
    return get_firestore().collection("sessions").document(session_id)


def user_session_id(chat_id: int, user_id: int, command_name: str) -> str:
    return f"{chat_id}:{user_id}:{command_name}"


def callback_session_id(
    chat_id: int, message_id: int, expense_id: str, action: str
) -> str:
    return f"{chat_id}:{message_id}:{expense_id}:{action}"


async def save(session: Session) -> None:
    session.updated_at = utcnow()

    def _set() -> None:
        _doc(session.session_id).set(session.model_dump(mode="json"))

    await run_in_thread(_set)


async def get(session_id: str) -> Optional[Session]:
    def _get() -> Optional[Session]:
        snap = _doc(session_id).get()
        if not snap.exists:
            return None
        return Session(**(snap.to_dict() or {}))

    return await run_in_thread(_get)


async def delete(session_id: str) -> None:
    def _del() -> None:
        _doc(session_id).delete()

    await run_in_thread(_del)
