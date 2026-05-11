"""Per-user share of an expense."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from ..utils.timeouts import utcnow


class ExpenseSplit(BaseModel):
    split_id: str  # normalized username; one split row per user per expense
    expense_id: str
    username: str
    telegram_user_id: Optional[int] = None
    amount_owed: Decimal
    percentage: Optional[Decimal] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    model_config = {"arbitrary_types_allowed": True}
