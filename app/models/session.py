"""Multi-step session state document."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..utils.timeouts import utcnow


class Session(BaseModel):
    session_id: str
    group_id: str
    chat_id: int
    user_id: Optional[int] = None
    message_id: Optional[int] = None
    callback_message_id: Optional[int] = None
    command_name: str
    step: str
    payload: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
