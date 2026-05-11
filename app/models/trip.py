"""Trip document model."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from ..utils.timeouts import utcnow


class Trip(BaseModel):
    trip_id: str
    group_id: str
    trip_name: str
    created_by_user_id: Optional[int] = None
    created_by_username: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
