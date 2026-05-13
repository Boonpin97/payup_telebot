"""Thin async client around the Telegram Bot HTTP API.

Why a custom client instead of aiogram / python-telegram-bot?  The bot only
needs a handful of methods (``sendMessage``, ``editMessageReplyMarkup``,
``answerCallbackQuery``, ``setWebhook``).  Using ``httpx`` directly keeps the
dependency surface small and the code easy to follow.
"""
from __future__ import annotations

from typing import Any

import httpx

from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TelegramAPIError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str | None = None, *, timeout: float = 10.0) -> None:
        token = token or get_settings().telegram_bot_token
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def call(self, method: str, **payload: Any) -> dict:
        url = f"{self._base_url}/{method}"
        # Drop None values; Telegram rejects them.
        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            resp = await self._client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.exception("telegram %s failed: %s", method, exc)
            raise TelegramAPIError(str(exc)) from exc
        data = resp.json()
        if not data.get("ok"):
            logger.warning("telegram %s returned not-ok: %s", method, data)
            raise TelegramAPIError(data.get("description", "unknown telegram error"))
        return data.get("result", {})

    # --- common methods --------------------------------------------------

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
        reply_to_message_id: int | None = None,
        disable_web_page_preview: bool | None = True,
    ) -> dict:
        return await self.call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
            disable_web_page_preview=disable_web_page_preview,
        )

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> dict:
        return await self.call(
            "editMessageText",
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        *,
        reply_markup: dict | None = None,
    ) -> dict:
        return await self.call(
            "editMessageReplyMarkup",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=reply_markup,
        )

    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict:
        return await self.call(
            "answerCallbackQuery",
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )

    async def set_webhook(
        self,
        url: str,
        *,
        secret_token: str | None = None,
        allowed_updates: list[str] | None = None,
    ) -> dict:
        return await self.call(
            "setWebhook",
            url=url,
            secret_token=secret_token,
            allowed_updates=allowed_updates,
        )

    async def set_my_commands(self, commands: list[dict]) -> dict:
        return await self.call("setMyCommands", commands=commands)


_client: TelegramClient | None = None


def get_telegram_client() -> TelegramClient:
    global _client
    if _client is None:
        _client = TelegramClient()
    return _client


async def shutdown_telegram_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
