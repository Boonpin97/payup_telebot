"""Settlement service tests."""
from __future__ import annotations

from decimal import Decimal

from app.services.settlement_service import compute_net_balances, simplify_debts
from app.utils.money import equal_split, sum_money


def test_equal_split_preserves_total_for_uneven_division():
    parts = equal_split(Decimal("10.00"), 3)
    assert sum_money(parts) == Decimal("10.00")
    # First two get the extra cent.
    assert parts == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]


def test_equal_split_clean_division():
    parts = equal_split(Decimal("9.00"), 3)
    assert parts == [Decimal("3.00"), Decimal("3.00"), Decimal("3.00")]


def test_compute_net_balances_basic():
    paid = {"alice": Decimal("150"), "bob": Decimal("100"), "charlie": Decimal("0")}
    owed = {"alice": Decimal("100"), "bob": Decimal("100"), "charlie": Decimal("50")}
    net = compute_net_balances(paid, owed)
    assert net == {
        "alice": Decimal("50.00"),
        "bob": Decimal("0.00"),
        "charlie": Decimal("-50.00"),
    }


def test_simplify_debts_two_party():
    net = {"alice": Decimal("50"), "charlie": Decimal("-50")}
    txns = simplify_debts(net)
    assert txns == [("charlie", "alice", Decimal("50.00"))]


def test_simplify_debts_minimises_transactions():
    # alice +60, bob +20, charlie -50, dave -30 -> expect 3 txns or fewer.
    net = {
        "alice": Decimal("60"),
        "bob": Decimal("20"),
        "charlie": Decimal("-50"),
        "dave": Decimal("-30"),
    }
    txns = simplify_debts(net)
    assert len(txns) <= 3
    # Net flow: each creditor receives exactly what they're owed.
    received = {}
    paid = {}
    for d, c, a in txns:
        received[c] = received.get(c, Decimal(0)) + a
        paid[d] = paid.get(d, Decimal(0)) + a
    assert received.get("alice") == Decimal("60")
    assert received.get("bob") == Decimal("20")
    assert paid.get("charlie") == Decimal("50")
    assert paid.get("dave") == Decimal("30")


def test_simplify_debts_all_zero_returns_empty():
    net = {"a": Decimal("0"), "b": Decimal("0")}
    assert simplify_debts(net) == []
