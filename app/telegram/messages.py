"""User-facing message templates.

All bot messages live here so wording can be tweaked in one place.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from ..utils.money import fmt
from ..utils.parser import display_username

GREETING = (
    "Hey everyone! I can help this group track and split trip expenses.\n\n"
    "To start a new trip, use:\n/new_trip"
)

ASK_TRIP_NAME = "What is the name of this trip?"

ASK_TRIP_MEMBERS = (
    "Who will be included in this trip?\n\n"
    "E.g.\n`@alice` `@bob` `@charlie`"
)

NO_ACTIVE_TRIP = (
    "No active trip found.\n\n"
    "Create one first using:\n/new_trip"
)

INVALID_AMOUNT = (
    "Invalid amount. Please enter a valid number, for example:\n10\n10.50"
)

ADD_EXPENSE_USAGE = "Please use this format:\n/add_expense pasta 10"

ASK_EXPENSE = (
    "Send the expense details.\n\n"
    "Format:\n<expense name> <amount> [@<name1> @<name2> ...]\n\n"
    "E.g.\npasta 10\npasta 10 `@alice` `@bob`"
)

EMPTY_TRIP_LIST = (
    "No trips found in this group.\n\n"
    "Create one using:\n/new_trip"
)

SESSION_EXPIRED = "This action has expired. Please start again."

EXPENSE_DELETED_SHORT = "Expense deleted."

EXPENSE_UPDATED = "Expense updated."

EDIT_ASK_NAME = "Please enter the new expense name."
EDIT_ASK_AMOUNT = "Please enter the new amount."
EDIT_ASK_PEOPLE = (
    "Please enter the people involved in this expense.\n\n"
    "Example:\n`@alice` `@bob`"
)

PARTIAL_AMOUNT_PROMPT = (
    "Enter the amount split.\n\n"
    "Format:\n`@alice` 10.29 `@bob` 20.50"
)
PARTIAL_PERCENT_PROMPT = (
    "Enter the percentage split.\n\n"
    "Format:\n`@alice` 40 `@bob` 60"
)

EDIT_MENU_PROMPT = "What else would you like to edit?"


def unknown_member(username: str) -> str:
    return (
        f"{display_username(username)} is not currently in this trip.\n\n"
        "Please add them first using:\n"
        f"/add_members {display_username(username)}"
    )


def trip_created(trip_name: str, members: Iterable[str]) -> str:
    member_lines = "\n".join(display_username(m) for m in members) or "(none)"
    return (
        f"Trip created: {trip_name}\n\n"
        f"Members:\n{member_lines}\n\n"
        "This is now the active trip.\n\n"
        "You can start adding expenses with:\n"
        "/add_expense pasta 10\n\n"
        "Or if you want to specify who is included in this transaction:\n"
        "/add_expense pasta 10 @alice @bob"
    )


def expense_added_all_members(name: str, amount: Decimal, payer: str) -> str:
    return (
        f"Expense added: {name}\n"
        f"Amount: {fmt(amount)}\n"
        f"Paid by: {display_username(payer)}\n"
        "Split between: all trip members\n"
        "Split type: Equal split"
    )


def expense_added_with_participants(
    name: str,
    amount: Decimal,
    payer: str,
    participants: Iterable[str],
    per_person: Decimal,
) -> str:
    member_lines = "\n".join(display_username(p) for p in participants)
    return (
        f"Expense added: {name}\n"
        f"Amount: {fmt(amount)}\n"
        f"Paid by: {display_username(payer)}\n"
        f"Split between:\n{member_lines}\n\n"
        f"Each person owes: {fmt(per_person)}"
    )


def expense_summary(
    name: str,
    amount: Decimal,
    payer: str,
    split_type: str,
    splits: list[tuple[str, Decimal]],
) -> str:
    lines = [f"{display_username(u)}: {fmt(a)}" for u, a in splits]
    return (
        f"Expense: {name}\n"
        f"Amount: {fmt(amount)}\n"
        f"Paid by: {display_username(payer)}\n"
        f"Split type: {split_type}\n"
        "Shares:\n" + "\n".join(lines)
    )


def members_added(
    added: list[str], already_present: list[str], current_members: list[str], trip_name: str
) -> str:
    parts: list[str] = []
    if added:
        parts.append("Members added:\n" + "\n".join(display_username(m) for m in added))
    for u in already_present:
        parts.append(f"{display_username(u)} is already in this trip.")
    parts.append(
        f"Current members in {trip_name}:\n"
        + ("\n".join(display_username(m) for m in current_members) or "(none)")
    )
    return "\n\n".join(parts)


def members_removed(
    removed: list[str], not_in_trip: list[str], current_members: list[str], trip_name: str
) -> str:
    parts: list[str] = []
    if removed:
        parts.append("Members removed:\n" + "\n".join(display_username(m) for m in removed))
    for u in not_in_trip:
        parts.append(f"{display_username(u)} is not in this trip.")
    parts.append(
        f"Current members in {trip_name}:\n"
        + ("\n".join(display_username(m) for m in current_members) or "(none)")
    )
    return "\n\n".join(parts)


def trip_summary(
    trip_name: str,
    members: list[str],
    total_spent: Decimal,
    paid_by: dict[str, Decimal],
    net_balance: dict[str, Decimal],
    settlements: list[tuple[str, str, Decimal]],
) -> str:
    member_lines = "\n".join(display_username(m) for m in members) or "(none)"
    paid_lines = (
        "\n".join(
            f"{display_username(u)} paid {fmt(paid_by.get(u, Decimal(0)))}"
            for u in members
        )
        or "(none)"
    )

    balance_lines: list[str] = []
    for u in members:
        bal = net_balance.get(u, Decimal(0))
        if bal > 0:
            balance_lines.append(f"{display_username(u)} should receive {fmt(bal)}")
        elif bal < 0:
            balance_lines.append(f"{display_username(u)} owes {fmt(-bal)}")
        else:
            balance_lines.append(f"{display_username(u)} is settled")
    balance_block = "\n".join(balance_lines) or "(none)"

    if settlements:
        settle_lines = "\n".join(
            f"{display_username(d)} pays {display_username(c)} {fmt(a)}"
            for d, c, a in settlements
        )
    else:
        settle_lines = "Everyone is settled."

    return (
        f"Trip Summary: {trip_name}\n\n"
        f"Members:\n{member_lines}\n\n"
        f"Total spent: {fmt(total_spent)}\n\n"
        f"Paid:\n{paid_lines}\n\n"
        f"Net Balance:\n{balance_block}\n\n"
        f"Simplified Settlement:\n{settle_lines}"
    )


def amount_split_mismatch(actual: Decimal, expected: Decimal) -> str:
    return (
        f"The custom split adds up to {fmt(actual)}, but the expense amount is {fmt(expected)}.\n\n"
        "Please enter the split again."
    )


def percentage_split_mismatch(actual: Decimal) -> str:
    return (
        f"The percentages add up to {fmt(actual)}%, but they must add up to 100%.\n\n"
        "Please enter the percentage split again."
    )


def trip_switched(trip_name: str, members: list[str]) -> str:
    member_lines = "\n".join(display_username(m) for m in members) or "(none)"
    return (
        f"Active trip switched to: {trip_name}\n\n"
        f"Current members:\n{member_lines}"
    )


def confirm_delete_trip_text(trip_name: str) -> str:
    return f"Are you sure you want to delete {trip_name}?"


def trip_deleted(trip_name: str) -> str:
    return f"Trip deleted: {trip_name}"


def equal_split_done(per_person: Decimal) -> str:
    return f"Expense updated to equal split.\nEach person owes: {fmt(per_person)}"
