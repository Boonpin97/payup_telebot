"""Decimal-safe money helpers.

Money is *always* stored and computed as ``Decimal``.  Floating point is never
used for monetary arithmetic.  Display values are rounded to 2 decimal places.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0")


def parse_money(raw: str) -> Decimal:
    """Parse a user-supplied amount.

    Raises ``ValueError`` for empty / malformed / non-positive input so the
    caller can return a friendly error message.
    """
    if raw is None:
        raise ValueError("amount missing")
    cleaned = raw.strip().replace(",", "")
    if not cleaned:
        raise ValueError("amount missing")
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid amount: {raw}") from exc
    if value <= 0:
        raise ValueError("amount must be positive")
    return quantize(value)


def parse_percentage(raw: str) -> Decimal:
    """Parse a percentage string (0 < pct <= 100)."""
    cleaned = raw.strip().rstrip("%").replace(",", "")
    if not cleaned:
        raise ValueError("percentage missing")
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid percentage: {raw}") from exc
    if value <= 0 or value > 100:
        raise ValueError("percentage must be between 0 and 100")
    return value


def quantize(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def fmt(value: Decimal) -> str:
    return f"{quantize(value):.2f}"


def equal_split(total: Decimal, n: int) -> list[Decimal]:
    """Split ``total`` equally between ``n`` people.

    Sum is preserved exactly: any rounding remainder is distributed one cent at
    a time to the earliest participants so the parts sum to ``total``.
    """
    if n <= 0:
        raise ValueError("cannot split among 0 people")
    total = quantize(total)
    cents_total = int((total * 100).to_integral_value(rounding=ROUND_HALF_UP))
    base = cents_total // n
    remainder = cents_total - base * n
    parts_cents = [base + (1 if i < remainder else 0) for i in range(n)]
    return [Decimal(c) / Decimal(100) for c in parts_cents]


def sum_money(values: Iterable[Decimal]) -> Decimal:
    total = ZERO
    for v in values:
        total += v
    return quantize(total)
