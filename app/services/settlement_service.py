"""Balance calculation and simplified-debt algorithm.

All money math uses ``Decimal``.  The simplified algorithm minimises the
number of transactions by repeatedly matching the largest debtor against the
largest creditor until everyone settles.
"""
from __future__ import annotations

from decimal import Decimal

from ..utils.money import ZERO, quantize


def compute_net_balances(
    paid_by: dict[str, Decimal], owed_by: dict[str, Decimal]
) -> dict[str, Decimal]:
    """``net_balance = paid - owed`` per user. Quantized to 2 dp."""
    users = set(paid_by.keys()) | set(owed_by.keys())
    return {
        u: quantize(paid_by.get(u, ZERO) - owed_by.get(u, ZERO))
        for u in users
    }


def simplify_debts(
    net_balances: dict[str, Decimal],
) -> list[tuple[str, str, Decimal]]:
    """Return ``[(debtor, creditor, amount)]`` to settle everyone.

    Approach: largest-debt-vs-largest-credit greedy. This is not provably
    optimal for arbitrary inputs (the general problem is NP-hard) but always
    produces N-1 or fewer transactions and is the algorithm used by Splitwise
    in practice. Cents are preserved exactly.
    """
    eps = Decimal("0.01")

    debtors: list[list] = sorted(
        ([u, -bal] for u, bal in net_balances.items() if bal < 0),
        key=lambda x: x[1],
        reverse=True,
    )
    creditors: list[list] = sorted(
        ([u, bal] for u, bal in net_balances.items() if bal > 0),
        key=lambda x: x[1],
        reverse=True,
    )

    settlements: list[tuple[str, str, Decimal]] = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        d_user, d_amt = debtors[i]
        c_user, c_amt = creditors[j]
        pay = quantize(min(d_amt, c_amt))
        if pay >= eps:
            settlements.append((d_user, c_user, pay))
        debtors[i][1] = quantize(d_amt - pay)
        creditors[j][1] = quantize(c_amt - pay)
        if debtors[i][1] < eps:
            i += 1
        if creditors[j][1] < eps:
            j += 1

    return settlements
