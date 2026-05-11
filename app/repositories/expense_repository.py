"""Expense + splits repository."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Iterable, Optional

from google.cloud.firestore_v1.base_query import FieldFilter

from ..models.expense import Expense
from ..models.split import ExpenseSplit
from ..utils.timeouts import utcnow
from .firestore_client import get_firestore, run_in_thread
from .group_repository import group_id_for_chat


def new_expense_id() -> str:
    return f"exp_{uuid.uuid4().hex[:12]}"


def _expenses_collection(chat_id: int, trip_id: str):
    return (
        get_firestore()
        .collection("groups")
        .document(group_id_for_chat(chat_id))
        .collection("trips")
        .document(trip_id)
        .collection("expenses")
    )


def _splits_collection(chat_id: int, trip_id: str, expense_id: str):
    return _expenses_collection(chat_id, trip_id).document(expense_id).collection("splits")


def _expense_to_doc(expense: Expense) -> dict:
    data = expense.model_dump(mode="json")
    data["amount"] = str(expense.amount)
    return data


def _split_to_doc(split: ExpenseSplit) -> dict:
    data = split.model_dump(mode="json")
    data["amount_owed"] = str(split.amount_owed)
    if split.percentage is not None:
        data["percentage"] = str(split.percentage)
    return data


def _expense_from_doc(data: dict) -> Expense:
    if isinstance(data.get("amount"), str):
        data["amount"] = Decimal(data["amount"])
    return Expense(**data)


def _split_from_doc(data: dict) -> ExpenseSplit:
    if isinstance(data.get("amount_owed"), str):
        data["amount_owed"] = Decimal(data["amount_owed"])
    if isinstance(data.get("percentage"), str):
        data["percentage"] = Decimal(data["percentage"])
    return ExpenseSplit(**data)


async def create_with_splits(
    chat_id: int,
    trip_id: str,
    expense: Expense,
    splits: Iterable[ExpenseSplit],
) -> None:
    """Create an expense and all its splits in a single batched write."""
    splits = list(splits)

    def _write() -> None:
        batch = get_firestore().batch()
        expense_ref = _expenses_collection(chat_id, trip_id).document(expense.expense_id)
        batch.set(expense_ref, _expense_to_doc(expense))
        splits_col = _splits_collection(chat_id, trip_id, expense.expense_id)
        for s in splits:
            batch.set(splits_col.document(s.split_id), _split_to_doc(s))
        batch.commit()

    await run_in_thread(_write)


async def replace_splits(
    chat_id: int,
    trip_id: str,
    expense: Expense,
    splits: Iterable[ExpenseSplit],
) -> None:
    """Atomically: update the expense doc and overwrite its splits sub-collection."""
    splits = list(splits)

    def _write() -> None:
        batch = get_firestore().batch()
        expense_ref = _expenses_collection(chat_id, trip_id).document(expense.expense_id)
        batch.set(expense_ref, _expense_to_doc(expense))
        splits_col = _splits_collection(chat_id, trip_id, expense.expense_id)
        # Delete existing splits, then write new ones.
        for doc in splits_col.stream():
            batch.delete(doc.reference)
        for s in splits:
            batch.set(splits_col.document(s.split_id), _split_to_doc(s))
        batch.commit()

    await run_in_thread(_write)


async def get(chat_id: int, trip_id: str, expense_id: str) -> Optional[Expense]:
    def _get() -> Optional[Expense]:
        snap = _expenses_collection(chat_id, trip_id).document(expense_id).get()
        if not snap.exists:
            return None
        return _expense_from_doc(snap.to_dict() or {})

    return await run_in_thread(_get)


async def list_active(chat_id: int, trip_id: str) -> list[Expense]:
    def _list() -> list[Expense]:
        q = _expenses_collection(chat_id, trip_id).where(
            filter=FieldFilter("is_deleted", "==", False)
        )
        out = [_expense_from_doc(doc.to_dict() or {}) for doc in q.stream()]
        out.sort(key=lambda e: e.created_at)
        return out

    return await run_in_thread(_list)


async def list_splits(
    chat_id: int, trip_id: str, expense_id: str
) -> list[ExpenseSplit]:
    def _list() -> list[ExpenseSplit]:
        return [
            _split_from_doc(doc.to_dict() or {})
            for doc in _splits_collection(chat_id, trip_id, expense_id).stream()
        ]

    return await run_in_thread(_list)


async def soft_delete(chat_id: int, trip_id: str, expense_id: str) -> None:
    def _delete() -> None:
        _expenses_collection(chat_id, trip_id).document(expense_id).update(
            {
                "is_deleted": True,
                "deleted_at": utcnow(),
                "updated_at": utcnow(),
            }
        )

    await run_in_thread(_delete)
