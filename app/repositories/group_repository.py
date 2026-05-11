"""Group document repository."""
from __future__ import annotations

from typing import Optional

from google.cloud import firestore

from ..models.group import Group
from ..utils.timeouts import utcnow
from .firestore_client import get_firestore, run_in_thread


def group_id_for_chat(chat_id: int) -> str:
    """Deterministic document ID derived from the Telegram chat ID."""
    return f"chat_{chat_id}"


def _doc(chat_id: int):
    return get_firestore().collection("groups").document(group_id_for_chat(chat_id))


async def get_or_create(chat_id: int, chat_title: Optional[str] = None) -> Group:
    def _txn() -> Group:
        ref = _doc(chat_id)
        snap = ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            data.setdefault("group_id", group_id_for_chat(chat_id))
            data.setdefault("telegram_chat_id", chat_id)
            return Group(**data)
        group = Group(
            group_id=group_id_for_chat(chat_id),
            telegram_chat_id=chat_id,
            chat_title=chat_title,
        )
        ref.set(group.model_dump(mode="json"))
        return group

    return await run_in_thread(_txn)


async def get(chat_id: int) -> Optional[Group]:
    def _get() -> Optional[Group]:
        snap = _doc(chat_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return Group(**data)

    return await run_in_thread(_get)


async def set_active_trip(chat_id: int, trip_id: Optional[str]) -> None:
    def _update() -> None:
        _doc(chat_id).update(
            {
                "active_trip_id": trip_id,
                "updated_at": utcnow(),
            }
        )

    await run_in_thread(_update)


async def set_active_trip_in_txn(
    txn: firestore.Transaction, chat_id: int, trip_id: Optional[str]
) -> None:
    def _update() -> None:
        txn.update(
            _doc(chat_id),
            {
                "active_trip_id": trip_id,
                "updated_at": utcnow(),
            },
        )

    await run_in_thread(_update)
