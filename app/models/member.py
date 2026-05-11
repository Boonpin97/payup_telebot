"""Trip member document model."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..utils.timeouts import utcnow


class Member(BaseModel):
    member_id: str  # normalized username (acts as deterministic ID)
    telegram_user_id: Optional[int] = None
    username: str  # normalized, no leading "@"
    display_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    removed_at: Optional[datetime] = None
