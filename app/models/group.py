"""Telegram group document model."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..utils.timeouts import utcnow


class Group(BaseModel):
    group_id: str
    telegram_chat_id: int
    chat_title: Optional[str] = None
    active_trip_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
