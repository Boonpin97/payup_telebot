"""Session helpers shared across command handlers.

All multi-step text-input flows are stored under a single chat-scoped session
key so that any user in the chat can answer the bot's prompt — matching the
spec ("Any user can reply with usernames" for /new_trip).

Callback-driven flows that don't require text input do not need a session;
they read the expense ID directly from the callback ``data``.
"""
from __future__ import annotations

from typing import Any, Optional

from ..models.session import Session
from ..repositories import group_repository
from ..services import session_service

# Per-chat input-pending session id.
INPUT = "input"


def chat_input_session_id(chat_id: int) -> str:
    return f"chat:{chat_id}:{INPUT}"


async def start_input(
    *,
    chat_id: int,
    command_name: str,
    step: str,
    payload: Optional[dict[str, Any]] = None,
    user_id: Optional[int] = None,
    callback_message_id: Optional[int] = None,
) -> Session:
    return await session_service.create(
        session_id=chat_input_session_id(chat_id),
        chat_id=chat_id,
        group_id=group_repository.group_id_for_chat(chat_id),
        command_name=command_name,
        step=step,
        payload=payload,
        user_id=user_id,
        callback_message_id=callback_message_id,
    )


async def get_alive_input(chat_id: int) -> Optional[Session]:
    return await session_service.get_if_alive(chat_input_session_id(chat_id))


async def end_input(chat_id: int) -> None:
    await session_service.end(chat_input_session_id(chat_id))
