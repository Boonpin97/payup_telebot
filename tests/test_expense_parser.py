"""Parser tests for /add_expense and split inputs."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.utils.parser import (
    parse_add_expense,
    parse_amount_split,
    parse_percentage_split,
    parse_usernames,
    normalize_username,
)


def test_normalize_username_lowercases_and_strips_at():
    assert normalize_username("@Alice") == "alice"
    assert normalize_username("BOB") == "bob"
    assert normalize_username("") == ""
    assert normalize_username("@bad name") == ""


def test_parse_usernames_dedupes_and_orders():
    assert parse_usernames("@a @b @a @c") == ["a", "b", "c"]
    assert parse_usernames("a, b , c") == ["a", "b", "c"]
    assert parse_usernames("") == []


def test_parse_add_expense_simple():
    args = parse_add_expense("pasta 10")
    assert args.name == "pasta"
    assert args.amount == Decimal("10.00")
    assert args.participants == []


def test_parse_add_expense_with_participants():
    args = parse_add_expense("pasta 10 @Alice @bob")
    assert args.name == "pasta"
    assert args.amount == Decimal("10.00")
    assert args.participants == ["alice", "bob"]


def test_parse_add_expense_multiword_name():
    args = parse_add_expense("dinner at marina 99.50 @alice")
    assert args.name == "dinner at marina"
    assert args.amount == Decimal("99.50")
    assert args.participants == ["alice"]


def test_parse_add_expense_missing_amount_raises():
    with pytest.raises(ValueError):
        parse_add_expense("pasta")


def test_parse_add_expense_invalid_amount_raises():
    with pytest.raises(ValueError):
        parse_add_expense("pasta abc")


def test_parse_add_expense_negative_amount_raises():
    with pytest.raises(ValueError):
        parse_add_expense("pasta -5")


def test_parse_add_expense_dedupes_participants():
    args = parse_add_expense("pasta 10 @a @a @b")
    assert args.participants == ["a", "b"]


def test_parse_amount_split_pairs():
    pairs = parse_amount_split("@alice 10.00 @bob 15.50")
    assert [(p.username, p.amount) for p in pairs] == [
        ("alice", Decimal("10.00")),
        ("bob", Decimal("15.50")),
    ]


def test_parse_amount_split_odd_tokens_raises():
    with pytest.raises(ValueError):
        parse_amount_split("@alice 10 @bob")


def test_parse_amount_split_duplicate_user_raises():
    with pytest.raises(ValueError):
        parse_amount_split("@alice 10 @alice 5")


def test_parse_percentage_split_pairs():
    pairs = parse_percentage_split("@alice 40 @bob 60")
    assert [(p.username, p.percent) for p in pairs] == [
        ("alice", Decimal("40")),
        ("bob", Decimal("60")),
    ]


def test_parse_percentage_split_rejects_over_100_value():
    with pytest.raises(ValueError):
        parse_percentage_split("@alice 150 @bob 60")
