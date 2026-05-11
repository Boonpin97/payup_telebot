"""Trip-level business logic."""
from __future__ import annotations

from typing import Optional

from ..models.member import Member
from ..models.trip import Trip
from ..repositories import (
    expense_repository,
    group_repository,
    member_repository,
    trip_repository,
)


async def create_trip(
    chat_id: int,
    chat_title: Optional[str],
    trip_name: str,
    member_usernames: list[str],
    *,
    created_by_user_id: Optional[int],
    created_by_username: Optional[str],
) -> Trip:
    """Create a new trip and set it as active."""
    await group_repository.get_or_create(chat_id, chat_title=chat_title)

    trip = Trip(
        trip_id=trip_repository.new_trip_id(),
        group_id=group_repository.group_id_for_chat(chat_id),
        trip_name=trip_name,
        created_by_user_id=created_by_user_id,
        created_by_username=created_by_username,
    )
    await trip_repository.create(chat_id, trip)

    if member_usernames:
        members = [Member(member_id=u, username=u) for u in member_usernames]
        await member_repository.upsert_many(chat_id, trip.trip_id, members)

    await group_repository.set_active_trip(chat_id, trip.trip_id)
    return trip


async def get_active_trip(chat_id: int) -> Optional[Trip]:
    group = await group_repository.get(chat_id)
    if not group or not group.active_trip_id:
        return None
    trip = await trip_repository.get(chat_id, group.active_trip_id)
    if trip is None or trip.is_deleted:
        return None
    return trip


async def list_trips(chat_id: int) -> list[Trip]:
    return await trip_repository.list_active(chat_id)


async def switch_active_trip(chat_id: int, trip_id: str) -> Optional[Trip]:
    trip = await trip_repository.get(chat_id, trip_id)
    if trip is None or trip.is_deleted:
        return None
    await group_repository.set_active_trip(chat_id, trip_id)
    return trip


async def delete_trip(chat_id: int, trip_id: str) -> Optional[Trip]:
    trip = await trip_repository.get(chat_id, trip_id)
    if trip is None or trip.is_deleted:
        return None

    await trip_repository.soft_delete(chat_id, trip_id)

    # Soft-delete all expenses (cheap: a small group's trip has dozens, not millions).
    expenses = await expense_repository.list_active(chat_id, trip_id)
    for e in expenses:
        await expense_repository.soft_delete(chat_id, trip_id, e.expense_id)

    # If the deleted trip was the active one, clear the active pointer.
    group = await group_repository.get(chat_id)
    if group and group.active_trip_id == trip_id:
        await group_repository.set_active_trip(chat_id, None)

    return trip
