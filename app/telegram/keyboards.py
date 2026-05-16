"""Inline keyboard builders.

Callback ``data`` values are short, structured strings parsed in
``commands.callbacks``.  Keep them under 64 bytes (Telegram limit).
"""
from __future__ import annotations

from typing import Iterable

# --- callback data namespace ----------------------------------------------
# Format: <action>:<expense_id>[:<extra>]
EXPENSE_EDIT = "exp_edit"
EXPENSE_DELETE = "exp_delete"
EXPENSE_PARTIAL = "exp_partial"

EDIT_NAME = "edit_name"
EDIT_AMOUNT = "edit_amount"
EDIT_PEOPLE = "edit_people"
EDIT_PARTIAL = "edit_partial"
EDIT_DONE = "edit_done"

SPLIT_EQUAL = "split_equal"
SPLIT_AMOUNT = "split_amount"
SPLIT_PERCENT = "split_percent"
EDIT_SPLIT_EQUAL = "edit_split_equal"
EDIT_SPLIT_AMOUNT = "edit_split_amount"
EDIT_SPLIT_PERCENT = "edit_split_percent"

DELETE_PAYMENT_PICK = "delpay"      # delpay:<expense_id>
EDIT_EXPENSE_PICK = "editexp"        # editexp:<expense_id>
SETTLE_PICK = "stl"                  # stl:<index> (index into simplified settlements)
SWITCH_TRIP_PICK = "switch"          # switch:<trip_id>
DELETE_TRIP_PICK = "deltrip"         # deltrip:<trip_id>
DELETE_TRIP_CONFIRM = "deltrip_yes"  # deltrip_yes:<trip_id>
DELETE_TRIP_CANCEL = "deltrip_no"    # deltrip_no:<trip_id>


def expense_actions(expense_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Edit", "callback_data": f"{EXPENSE_EDIT}:{expense_id}"},
                {"text": "Delete", "callback_data": f"{EXPENSE_DELETE}:{expense_id}"},
                {"text": "Partial Split", "callback_data": f"{EXPENSE_PARTIAL}:{expense_id}"},
            ]
        ]
    }


def edit_menu(expense_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Name", "callback_data": f"{EDIT_NAME}:{expense_id}"},
                {"text": "Amount", "callback_data": f"{EDIT_AMOUNT}:{expense_id}"},
            ],
            [
                {"text": "People", "callback_data": f"{EDIT_PEOPLE}:{expense_id}"},
                {"text": "Split Type", "callback_data": f"{EDIT_PARTIAL}:{expense_id}"},
            ],
            [
                {"text": "Done", "callback_data": f"{EDIT_DONE}:{expense_id}"},
            ],
        ]
    }


def partial_split_menu(expense_id: str, *, source: str = "direct") -> dict:
    if source == "edit":
        equal_action = EDIT_SPLIT_EQUAL
        amount_action = EDIT_SPLIT_AMOUNT
        percent_action = EDIT_SPLIT_PERCENT
    else:
        equal_action = SPLIT_EQUAL
        amount_action = SPLIT_AMOUNT
        percent_action = SPLIT_PERCENT
    return {
        "inline_keyboard": [
            [
                {"text": "Equal Split", "callback_data": f"{equal_action}:{expense_id}"},
                {"text": "Amount Split", "callback_data": f"{amount_action}:{expense_id}"},
                {"text": "% Split", "callback_data": f"{percent_action}:{expense_id}"},
            ]
        ]
    }


def expense_pick_keyboard(items: Iterable[tuple[str, str]]) -> dict:
    """Build a vertical list of buttons for /delete_payment.

    ``items`` is an iterable of ``(label, expense_id)`` tuples.
    """
    rows = [
        [{"text": label, "callback_data": f"{DELETE_PAYMENT_PICK}:{expense_id}"}]
        for label, expense_id in items
    ]
    return {"inline_keyboard": rows}


def edit_expense_pick_keyboard(items: Iterable[tuple[str, str]]) -> dict:
    """Build a vertical list of buttons for /edit_expense.

    ``items`` is an iterable of ``(label, expense_id)`` tuples.
    """
    rows = [
        [{"text": label, "callback_data": f"{EDIT_EXPENSE_PICK}:{expense_id}"}]
        for label, expense_id in items
    ]
    return {"inline_keyboard": rows}


def settle_pick_keyboard(labels: Iterable[str]) -> dict:
    """Build a vertical list of buttons for /settle.

    Each button's callback data carries only the index into the simplified
    settlements list (e.g. ``stl:0``). The debtor/creditor/amount is
    recomputed when the button is tapped so the displayed debts can be
    longer than Telegram's 64-byte callback-data limit and so that stale
    button presses settle the *current* corresponding debt.
    """
    rows = [
        [{"text": label, "callback_data": f"{SETTLE_PICK}:{idx}"}]
        for idx, label in enumerate(labels)
    ]
    return {"inline_keyboard": rows}


def trip_pick_keyboard(
    items: Iterable[tuple[str, str]], *, action: str
) -> dict:
    """Build a vertical list of buttons for /switch_trip or /delete_trip.

    ``action`` should be ``SWITCH_TRIP_PICK`` or ``DELETE_TRIP_PICK``.
    """
    rows = [
        [{"text": label, "callback_data": f"{action}:{trip_id}"}]
        for label, trip_id in items
    ]
    return {"inline_keyboard": rows}


def confirm_delete_trip(trip_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Yes, Delete", "callback_data": f"{DELETE_TRIP_CONFIRM}:{trip_id}"},
                {"text": "Cancel", "callback_data": f"{DELETE_TRIP_CANCEL}:{trip_id}"},
            ]
        ]
    }
