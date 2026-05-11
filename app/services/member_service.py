"""Member-related business logic."""
from __future__ import annotations

from dataclasses import dataclass

from ..models.member import Member
from ..repositories import member_repository
from ..utils.timeouts import utcnow


@dataclass
class AddMembersResult:
    added: list[str]
    already_present: list[str]
    current_members: list[str]


@dataclass
class RemoveMembersResult:
    removed: list[str]
    not_in_trip: list[str]
    current_members: list[str]


async def add_members(
    chat_id: int, trip_id: str, usernames: list[str]
) -> AddMembersResult:
    existing = {m.username: m for m in await member_repository.list_all(chat_id, trip_id)}

    added: list[str] = []
    already_present: list[str] = []
    to_write: list[Member] = []

    for username in usernames:
        prev = existing.get(username)
        if prev and prev.is_active:
            already_present.append(username)
            continue
        if prev and not prev.is_active:
            # Reactivate previously-removed member.
            prev.is_active = True
            prev.removed_at = None
            prev.updated_at = utcnow()
            to_write.append(prev)
            added.append(username)
            continue
        new = Member(member_id=username, username=username)
        to_write.append(new)
        added.append(username)

    if to_write:
        await member_repository.upsert_many(chat_id, trip_id, to_write)

    current = [
        m.username for m in await member_repository.list_active(chat_id, trip_id)
    ]
    return AddMembersResult(
        added=added,
        already_present=already_present,
        current_members=current,
    )


async def remove_members(
    chat_id: int, trip_id: str, usernames: list[str]
) -> RemoveMembersResult:
    active = {
        m.username: m for m in await member_repository.list_active(chat_id, trip_id)
    }
    removed: list[str] = []
    not_in_trip: list[str] = []
    for u in usernames:
        if u not in active:
            not_in_trip.append(u)
            continue
        await member_repository.deactivate(chat_id, trip_id, u)
        removed.append(u)

    current = [
        m.username for m in await member_repository.list_active(chat_id, trip_id)
    ]
    return RemoveMembersResult(
        removed=removed,
        not_in_trip=not_in_trip,
        current_members=current,
    )


async def active_usernames(chat_id: int, trip_id: str) -> list[str]:
    return [m.username for m in await member_repository.list_active(chat_id, trip_id)]
