"""Shared types passed to command handlers.

A ``CommandContext`` bundles the parsed Telegram update fields most handlers
need (chat, sender, raw text), plus a Telegram client for sending replies.
This keeps each handler signature small and uniform.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..telegram.bot import TelegramClient


@dataclass
class CommandContext:
    chat_id: int
    chat_title: Optional[str]
    user_id: Optional[int]
    username: Optional[str]  # normalized, no leading @; empty if unknown
    message_id: Optional[int]
    raw_text: str
    args_text: str
    client: TelegramClient


@dataclass
class CallbackContext:
    chat_id: int
    user_id: Optional[int]
    username: Optional[str]
    message_id: int
    callback_query_id: str
    data: str
    client: TelegramClient
