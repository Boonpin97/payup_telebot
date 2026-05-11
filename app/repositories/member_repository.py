"""Trip member repository."""
from __future__ import annotations

from typing import Iterable, Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from ..models.member import Member
from ..utils.timeouts import utcnow
from .firestore_client import get_firestore, run_in_thread
from .group_repository import group_id_for_chat


def _members_collection(chat_id: int, trip_id: str):
    return (
        get_firestore()
        .collection("groups")
        .document(group_id_for_chat(chat_id))
        .collection("trips")
        .document(trip_id)
        .collection("members")
    )


async def upsert_many(
    chat_id: int,
    trip_id: str,
    members: Iterable[Member],
) -> None:
    members = list(members)
    if not members:
        return

    def _write() -> None:
        batch = get_firestore().batch()
        col = _members_collection(chat_id, trip_id)
        for m in members:
            batch.set(col.document(m.member_id), m.model_dump(mode="json"))
        batch.commit()

    await run_in_thread(_write)


async def list_active(chat_id: int, trip_id: str) -> list[Member]:
    def _list() -> list[Member]:
        q = _members_collection(chat_id, trip_id).where(
            filter=FieldFilter("is_active", "==", True)
        )
        members = [Member(**(doc.to_dict() or {})) for doc in q.stream()]
        members.sort(key=lambda m: m.created_at)
        return members

    return await run_in_thread(_list)


async def list_all(chat_id: int, trip_id: str) -> list[Member]:
    def _list() -> list[Member]:
        members = [
            Member(**(doc.to_dict() or {}))
            for doc in _members_collection(chat_id, trip_id).stream()
        ]
        members.sort(key=lambda m: m.created_at)
        return members

    return await run_in_thread(_list)


async def get(chat_id: int, trip_id: str, username: str) -> Optional[Member]:
    def _get() -> Optional[Member]:
        snap = _members_collection(chat_id, trip_id).document(username).get()
        if not snap.exists:
            return None
        return Member(**(snap.to_dict() or {}))

    return await run_in_thread(_get)


async def deactivate(chat_id: int, trip_id: str, username: str) -> None:
    def _update() -> None:
        _members_collection(chat_id, trip_id).document(username).update(
            {
                "is_active": False,
                "removed_at": utcnow(),
                "updated_at": utcnow(),
            }
        )

    await run_in_thread(_update)
