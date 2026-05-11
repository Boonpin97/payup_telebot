"""Member service tests using an in-memory fake repository.

Patches ``app.services.member_service.member_repository`` so the service can be
exercised without touching Firestore.
"""
from __future__ import annotations

import pytest

from app.models.member import Member
from app.services import member_service


class FakeMemberRepo:
    def __init__(self) -> None:
        self.store: dict[tuple[int, str], dict[str, Member]] = {}

    async def list_all(self, chat_id: int, trip_id: str) -> list[Member]:
        return list(self.store.get((chat_id, trip_id), {}).values())

    async def list_active(self, chat_id: int, trip_id: str) -> list[Member]:
        return [m for m in await self.list_all(chat_id, trip_id) if m.is_active]

    async def upsert_many(self, chat_id: int, trip_id: str, members) -> None:
        bucket = self.store.setdefault((chat_id, trip_id), {})
        for m in members:
            bucket[m.username] = m

    async def deactivate(self, chat_id: int, trip_id: str, username: str) -> None:
        bucket = self.store.setdefault((chat_id, trip_id), {})
        if username in bucket:
            m = bucket[username]
            m.is_active = False


@pytest.fixture
def fake_repo(monkeypatch):
    repo = FakeMemberRepo()
    monkeypatch.setattr(member_service, "member_repository", repo)
    return repo


@pytest.mark.asyncio
async def test_add_members_dedupes_and_reports_already_present(fake_repo):
    result = await member_service.add_members(1, "trip1", ["alice", "bob"])
    assert sorted(result.added) == ["alice", "bob"]
    assert result.already_present == []
    assert sorted(result.current_members) == ["alice", "bob"]

    again = await member_service.add_members(1, "trip1", ["alice", "carol"])
    assert again.added == ["carol"]
    assert again.already_present == ["alice"]
    assert sorted(again.current_members) == ["alice", "bob", "carol"]


@pytest.mark.asyncio
async def test_add_members_reactivates_removed_member(fake_repo):
    await member_service.add_members(1, "t", ["alice"])
    await member_service.remove_members(1, "t", ["alice"])
    assert await fake_repo.list_active(1, "t") == []

    result = await member_service.add_members(1, "t", ["alice"])
    assert result.added == ["alice"]
    assert result.current_members == ["alice"]


@pytest.mark.asyncio
async def test_remove_members_reports_not_in_trip(fake_repo):
    await member_service.add_members(1, "t", ["alice"])
    result = await member_service.remove_members(1, "t", ["alice", "bob"])
    assert result.removed == ["alice"]
    assert result.not_in_trip == ["bob"]
    assert result.current_members == []
