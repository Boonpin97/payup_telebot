"""Expense and split business logic."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ..config import get_settings
from ..models.expense import Expense, SplitType
from ..models.split import ExpenseSplit
from ..repositories import expense_repository, member_repository
from ..utils.money import ZERO, equal_split, quantize, sum_money
from . import settlement_service


class ExpenseError(ValueError):
    """Raised for user-facing validation problems."""


@dataclass
class CreatedExpense:
    expense: Expense
    splits: list[ExpenseSplit]


async def add_expense(
    *,
    chat_id: int,
    trip_id: str,
    group_id: str,
    name: str,
    amount: Decimal,
    paid_by_user_id: Optional[int],
    paid_by_username: str,
    participants: list[str],
) -> CreatedExpense:
    """Create an expense with an equal split among ``participants``.

    If ``participants`` is empty, all active trip members are used.
    Validates that every listed participant is currently in the trip.
    """
    active_members = await member_repository.list_active(chat_id, trip_id)
    active_usernames = [m.username for m in active_members]
    member_id_map = {m.username: m.telegram_user_id for m in active_members}

    if not participants:
        participants = list(active_usernames)
        if not participants:
            raise ExpenseError(
                "There are no members in this trip yet. Add some with /add_members."
            )

    # Validate every participant exists.
    active_set = set(active_usernames)
    for u in participants:
        if u not in active_set:
            raise ExpenseError(u)

    # Make sure the payer is also in the trip; if not, they're auto-added
    # when they ran /add_expense (they're the command sender).
    if paid_by_username not in active_set:
        raise ExpenseError(paid_by_username)

    expense = Expense(
        expense_id=expense_repository.new_expense_id(),
        trip_id=trip_id,
        group_id=group_id,
        expense_name=name,
        amount=quantize(amount),
        currency=get_settings().default_currency,
        paid_by_user_id=paid_by_user_id,
        paid_by_username=paid_by_username,
        participant_usernames=participants,
        split_type="equal",
        created_by_user_id=paid_by_user_id,
        created_by_username=paid_by_username,
    )
    splits = _equal_splits(expense, participants, member_id_map)
    await expense_repository.create_with_splits(chat_id, trip_id, expense, splits)
    return CreatedExpense(expense=expense, splits=splits)


def _equal_splits(
    expense: Expense,
    participants: list[str],
    user_id_map: dict[str, Optional[int]],
) -> list[ExpenseSplit]:
    parts = equal_split(expense.amount, len(participants))
    return [
        ExpenseSplit(
            split_id=u,
            expense_id=expense.expense_id,
            username=u,
            telegram_user_id=user_id_map.get(u),
            amount_owed=quantize(p),
        )
        for u, p in zip(participants, parts)
    ]


async def replace_split_equal(
    chat_id: int, trip_id: str, expense: Expense
) -> list[ExpenseSplit]:
    """Reset to an equal split among the current participants."""
    members = await member_repository.list_active(chat_id, trip_id)
    user_id_map = {m.username: m.telegram_user_id for m in members}
    expense.split_type = "equal"
    splits = _equal_splits(expense, expense.participant_usernames, user_id_map)
    await expense_repository.replace_splits(chat_id, trip_id, expense, splits)
    return splits


async def replace_split_amounts(
    chat_id: int,
    trip_id: str,
    expense: Expense,
    user_amounts: list[tuple[str, Decimal]],
) -> list[ExpenseSplit]:
    """Apply a custom amount split.

    Validates the totals match and every user is a participant.
    """
    participant_set = set(expense.participant_usernames)
    for u, _ in user_amounts:
        if u not in participant_set:
            raise ExpenseError(f"@{u} is not part of this expense")

    total = sum_money(a for _, a in user_amounts)
    if total != expense.amount:
        raise ExpenseError("amount_mismatch")

    members = await member_repository.list_active(chat_id, trip_id)
    user_id_map = {m.username: m.telegram_user_id for m in members}

    expense.split_type = "amount"
    splits = [
        ExpenseSplit(
            split_id=u,
            expense_id=expense.expense_id,
            username=u,
            telegram_user_id=user_id_map.get(u),
            amount_owed=quantize(a),
        )
        for u, a in user_amounts
    ]
    await expense_repository.replace_splits(chat_id, trip_id, expense, splits)
    return splits


async def replace_split_percentages(
    chat_id: int,
    trip_id: str,
    expense: Expense,
    user_percents: list[tuple[str, Decimal]],
) -> list[ExpenseSplit]:
    """Apply a custom percentage split.

    Validates that percentages sum to 100 and every user is a participant.
    """
    participant_set = set(expense.participant_usernames)
    for u, _ in user_percents:
        if u not in participant_set:
            raise ExpenseError(f"@{u} is not part of this expense")

    total = sum(p for _, p in user_percents)
    if total != Decimal("100"):
        raise ExpenseError("percent_mismatch")

    members = await member_repository.list_active(chat_id, trip_id)
    user_id_map = {m.username: m.telegram_user_id for m in members}

    # Convert percentages to amounts in cents to preserve the total exactly,
    # distributing any rounding remainder one cent at a time.
    cents_total = int((expense.amount * 100).to_integral_value())
    cent_parts = [
        int((Decimal(cents_total) * p / Decimal(100)).quantize(Decimal("1")))
        for _, p in user_percents
    ]
    diff = cents_total - sum(cent_parts)
    i = 0
    while diff != 0 and cent_parts:
        step = 1 if diff > 0 else -1
        cent_parts[i % len(cent_parts)] += step
        diff -= step
        i += 1
    amounts = [Decimal(c) / Decimal(100) for c in cent_parts]

    expense.split_type = "percentage"
    splits = [
        ExpenseSplit(
            split_id=u,
            expense_id=expense.expense_id,
            username=u,
            telegram_user_id=user_id_map.get(u),
            amount_owed=quantize(a),
            percentage=p,
        )
        for (u, p), a in zip(user_percents, amounts)
    ]
    await expense_repository.replace_splits(chat_id, trip_id, expense, splits)
    return splits


async def add_settlement(
    *,
    chat_id: int,
    trip_id: str,
    group_id: str,
    payer_user_id: Optional[int],
    payer_username: str,
    recipient_username: str,
    amount: Decimal,
) -> Expense:
    """Record that payer paid recipient outside the app.

    Stored as a special expense (``is_settlement=True``) so the balance math
    works without a separate data model: paid_by[payer] and owed_by[recipient]
    both go up by ``amount``, reducing the net debt between them.
    """
    active_members = await member_repository.list_active(chat_id, trip_id)
    active_set = {m.username for m in active_members}
    member_id_map = {m.username: m.telegram_user_id for m in active_members}

    for u in (payer_username, recipient_username):
        if u not in active_set:
            raise ExpenseError(u)

    expense = Expense(
        expense_id=expense_repository.new_expense_id(),
        trip_id=trip_id,
        group_id=group_id,
        expense_name="Settlement",
        amount=quantize(amount),
        currency=get_settings().default_currency,
        paid_by_user_id=payer_user_id,
        paid_by_username=payer_username,
        participant_usernames=[recipient_username],
        split_type="equal",
        is_settlement=True,
        created_by_user_id=payer_user_id,
        created_by_username=payer_username,
    )
    split = ExpenseSplit(
        split_id=recipient_username,
        expense_id=expense.expense_id,
        username=recipient_username,
        telegram_user_id=member_id_map.get(recipient_username),
        amount_owed=quantize(amount),
    )
    await expense_repository.create_with_splits(chat_id, trip_id, expense, [split])
    return expense


async def delete_expense(chat_id: int, trip_id: str, expense_id: str) -> None:
    await expense_repository.soft_delete(chat_id, trip_id, expense_id)


# --- summary aggregation -------------------------------------------------


@dataclass
class TripSummary:
    members: list[str]
    total_spent: Decimal
    paid_by: dict[str, Decimal]
    owed_by: dict[str, Decimal]
    net_balance: dict[str, Decimal]
    settlements: list[tuple[str, str, Decimal]]


async def compute_summary(chat_id: int, trip_id: str) -> TripSummary:
    members = await member_repository.list_active(chat_id, trip_id)
    member_usernames = [m.username for m in members]

    expenses = await expense_repository.list_active(chat_id, trip_id)
    paid_by: dict[str, Decimal] = {u: ZERO for u in member_usernames}
    owed_by: dict[str, Decimal] = {u: ZERO for u in member_usernames}
    total = ZERO

    for e in expenses:
        if not e.is_settlement:
            total += e.amount
        paid_by[e.paid_by_username] = paid_by.get(e.paid_by_username, ZERO) + e.amount
        splits = await expense_repository.list_splits(chat_id, trip_id, e.expense_id)
        for s in splits:
            owed_by[s.username] = owed_by.get(s.username, ZERO) + s.amount_owed

    paid_by = {u: quantize(v) for u, v in paid_by.items()}
    owed_by = {u: quantize(v) for u, v in owed_by.items()}
    net = settlement_service.compute_net_balances(paid_by, owed_by)
    settlements = settlement_service.simplify_debts(net)

    return TripSummary(
        members=member_usernames,
        total_spent=quantize(total),
        paid_by=paid_by,
        owed_by=owed_by,
        net_balance=net,
        settlements=settlements,
    )
