"""Text parsers for Telegram command arguments.

These functions are pure — no Telegram or Firestore imports — so they're easy
to unit test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from .money import parse_money, parse_percentage

_USERNAME_RE = re.compile(r"^@?([A-Za-z0-9_]{1,32})$")


def normalize_username(raw: str) -> str:
    """Strip leading ``@`` and lowercase. Returns "" for unparseable input."""
    if not raw:
        return ""
    cleaned = raw.strip()
    if not cleaned:
        return ""
    m = _USERNAME_RE.match(cleaned)
    if not m:
        return ""
    return m.group(1).lower()


def display_username(name: str) -> str:
    """Render a normalized username for output (always with leading ``@``)."""
    return f"@{name}" if not name.startswith("@") else name


def parse_usernames(raw: str) -> list[str]:
    """Extract a list of normalized usernames from free-form text."""
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for token in raw.replace(",", " ").split():
        n = normalize_username(token)
        if not n or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


@dataclass
class AddExpenseArgs:
    name: str
    amount: Decimal
    participants: list[str]  # normalized usernames; empty -> "all members"


def parse_add_expense(args_text: str) -> AddExpenseArgs:
    """Parse ``/add_expense <name> <amount> [@user ...]``.

    Rules:
      - Tokens are whitespace-separated.
      - All trailing ``@username`` tokens form the participant list.
      - The token immediately before the participants must be a valid number
        (the amount).
      - Everything before that is concatenated with spaces as the expense name.
    """
    if not args_text or not args_text.strip():
        raise ValueError("missing arguments")

    tokens = args_text.strip().split()
    # Peel trailing @usernames.
    participants: list[str] = []
    while tokens and tokens[-1].startswith("@"):
        n = normalize_username(tokens.pop())
        if n:
            participants.insert(0, n)

    seen: set[str] = set()
    deduped: list[str] = []
    for u in participants:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    participants = deduped

    if len(tokens) < 2:
        raise ValueError("expected '<name> <amount>'")

    amount = parse_money(tokens[-1])
    name = " ".join(tokens[:-1]).strip()
    if not name:
        raise ValueError("missing expense name")

    return AddExpenseArgs(name=name, amount=amount, participants=participants)


@dataclass
class UserAmount:
    username: str
    amount: Decimal


@dataclass
class UserPercent:
    username: str
    percent: Decimal


def parse_amount_split(raw: str) -> list[UserAmount]:
    """Parse ``@user1 10.00 @user2 20.00`` into pairs."""
    pairs = _parse_user_value_pairs(raw, parse_money, "amount")
    return [UserAmount(username=u, amount=v) for u, v in pairs]


def parse_percentage_split(raw: str) -> list[UserPercent]:
    """Parse ``@user1 40 @user2 60`` into pairs."""
    pairs = _parse_user_value_pairs(raw, parse_percentage, "percentage")
    return [UserPercent(username=u, percent=v) for u, v in pairs]


def parse_settle(args_text: str) -> tuple[str, Decimal]:
    """Parse ``/settle @username amount`` → ``(username, amount)``."""
    tokens = args_text.strip().split()
    if len(tokens) < 2:
        raise ValueError("expected '@username amount'")
    username = normalize_username(tokens[0])
    if not username:
        raise ValueError(f"invalid username: {tokens[0]}")
    amount = parse_money(tokens[1])
    return username, amount


def _parse_user_value_pairs(
    raw: str,
    value_parser: Callable[[str], Decimal],
    value_label: str,
) -> list[tuple[str, Decimal]]:
    if not raw or not raw.strip():
        raise ValueError("input is empty")
    tokens = raw.replace(",", " ").split()
    if len(tokens) % 2 != 0:
        raise ValueError(
            f"expected pairs of '@user {value_label}', got odd number of tokens"
        )

    seen: set[str] = set()
    out: list[tuple[str, Decimal]] = []
    for i in range(0, len(tokens), 2):
        username_token, value_token = tokens[i], tokens[i + 1]
        username = normalize_username(username_token)
        if not username:
            raise ValueError(f"invalid username: {username_token}")
        if username in seen:
            raise ValueError(f"duplicate user: @{username}")
        seen.add(username)
        value = value_parser(value_token)
        out.append((username, value))
    return out
