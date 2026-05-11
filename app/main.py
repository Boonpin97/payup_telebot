"""FastAPI entrypoint for the Telegram trip-split bot."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .config import get_settings
from .telegram.bot import shutdown_telegram_client
from .telegram.webhook import handle_update
from .utils.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await shutdown_telegram_client()


app = FastAPI(title="Trip Split Bot", lifespan=lifespan)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/webhook")
async def webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    if not _verify_secret(x_telegram_bot_api_secret_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid secret token",
        )
    try:
        update = await request.json()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid json")

    # Telegram retries on non-2xx — swallow handler exceptions and log them
    # so a single broken update doesn't generate retries.
    try:
        await handle_update(update)
    except Exception:  # noqa: BLE001
        logger.exception("error handling update %s", update.get("update_id"))
    return JSONResponse({"ok": True})


def _verify_secret(header_value: str | None) -> bool:
    expected = settings.telegram_webhook_secret
    if not expected:
        # No secret configured: only accept in development to ease local testing.
        return settings.environment != "production"
    return header_value is not None and header_value == expected
