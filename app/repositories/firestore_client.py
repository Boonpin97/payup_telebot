"""Singleton wrapper around the Google Cloud Firestore client.

The synchronous client is used and offloaded to a worker thread when called
from async code (Firestore's async client requires gRPC + extra deps; the
sync client is more than adequate for this workload).
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

from google.cloud import firestore

from ..config import get_settings

T = TypeVar("T")

_client: firestore.Client | None = None


def get_firestore() -> firestore.Client:
    global _client
    if _client is None:
        settings = get_settings()
        kwargs: dict[str, Any] = {}
        if settings.google_cloud_project:
            kwargs["project"] = settings.google_cloud_project
        if settings.firestore_database_id and settings.firestore_database_id != "(default)":
            kwargs["database"] = settings.firestore_database_id
        _client = firestore.Client(**kwargs)
    return _client


async def run_in_thread(func: Callable[..., T], *args, **kwargs) -> T:
    """Offload a sync Firestore call to the default thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
