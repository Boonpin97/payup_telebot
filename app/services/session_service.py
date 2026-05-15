"""Session lifecycle helpers.

Wraps the session repository with expiry and TTL handling.  Callers should
always go through this module rather than the repository directly so the
3-minute timeout is enforced consistently.
"""
from __future__ import annotations

from typing import Any, Optional

from ..config import get_settings
from ..models.session import Session
from ..repositories import session_repository
from ..utils.timeouts import expires_at, is_expired, utcnow


async def create(
    *,
    session_id: str,
    chat_id: int,
    group_id: str,
    command_name: str,
    step: str,
    payload: Optional[dict[str, Any]] = None,
    user_id: Optional[int] = None,
    message_id: Optional[int] = None,
    callback_message_id: Optional[int] = None,
) -> Session:
    settings = get_settings()
    sess = Session(
        session_id=session_id,
        group_id=group_id,
        chat_id=chat_id,
        user_id=user_id,
        message_id=message_id,
        callback_message_id=callback_message_id,
        command_name=command_name,
        step=step,
        payload=payload or {},
        expires_at=expires_at(settings.session_ttl_seconds),
    )
    await session_repository.save(sess)
    return sess


async def get_if_alive(session_id: str) -> tuple[Optional[Session], bool]:
    """Return ``(session, expired)``.

    ``session`` is non-None only when the session is alive.
    ``expired`` is True when the document existed but the TTL had passed.
    """
    sess = await session_repository.get(session_id)
    if sess is None:
        return None, False
    if is_expired(sess.expires_at):
        await session_repository.delete(session_id)
        return None, True
    return sess, False


async def update(sess: Session, *, step: Optional[str] = None, payload: Optional[dict[str, Any]] = None) -> Session:
    """Update step / payload and refresh the expiry."""
    if step is not None:
        sess.step = step
    if payload is not None:
        sess.payload = payload
    sess.expires_at = expires_at(get_settings().session_ttl_seconds)
    sess.updated_at = utcnow()
    await session_repository.save(sess)
    return sess


async def end(session_id: str) -> None:
    await session_repository.delete(session_id)
