"""Trip document repository."""
from __future__ import annotations

import uuid
from typing import Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from ..models.trip import Trip
from ..utils.timeouts import utcnow
from .firestore_client import get_firestore, run_in_thread
from .group_repository import group_id_for_chat


def _trips_collection(chat_id: int):
    return (
        get_firestore()
        .collection("groups")
        .document(group_id_for_chat(chat_id))
        .collection("trips")
    )


async def create(chat_id: int, trip: Trip) -> Trip:
    def _create() -> Trip:
        trip_dict = trip.model_dump(mode="json")
        _trips_collection(chat_id).document(trip.trip_id).set(trip_dict)
        return trip

    return await run_in_thread(_create)


def new_trip_id() -> str:
    return f"trip_{uuid.uuid4().hex[:12]}"


async def get(chat_id: int, trip_id: str) -> Optional[Trip]:
    def _get() -> Optional[Trip]:
        snap = _trips_collection(chat_id).document(trip_id).get()
        if not snap.exists:
            return None
        return Trip(**(snap.to_dict() or {}))

    return await run_in_thread(_get)


async def list_active(chat_id: int) -> list[Trip]:
    def _list() -> list[Trip]:
        q = _trips_collection(chat_id).where(
            filter=FieldFilter("is_deleted", "==", False)
        )
        return [Trip(**(doc.to_dict() or {})) for doc in q.stream()]

    return await run_in_thread(_list)


async def soft_delete(chat_id: int, trip_id: str) -> None:
    def _delete() -> None:
        _trips_collection(chat_id).document(trip_id).update(
            {
                "is_deleted": True,
                "deleted_at": utcnow(),
                "updated_at": utcnow(),
            }
        )

    await run_in_thread(_delete)
