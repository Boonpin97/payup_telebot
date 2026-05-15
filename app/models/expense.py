"""Expense document model."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from ..utils.timeouts import utcnow

SplitType = Literal["equal", "amount", "percentage"]


class Expense(BaseModel):
    expense_id: str
    trip_id: str
    group_id: str
    expense_name: str
    amount: Decimal
    currency: str = "SGD"
    paid_by_user_id: Optional[int] = None
    paid_by_username: str
    participant_usernames: list[str] = Field(default_factory=list)
    split_type: SplitType = "equal"
    created_by_user_id: Optional[int] = None
    created_by_username: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    is_settlement: bool = False
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    model_config = {"arbitrary_types_allowed": True}
