# CLAUDE.md

## Project Overview

This project is a Telegram group chat bot for trip expense splitting. It works like a lightweight Splitwise inside Telegram groups.

The bot lets users create trips, add members, add expenses, split expenses equally or partially, view summaries, list expenses, record settlements, and calculate simplified debt settlement.

## Architecture

Telegram webhook -> FastAPI backend on Cloud Run -> Firestore database.

The backend runs in Docker and is deployed to Google Cloud Run.

## Core Rules

- One Telegram group can have multiple trips.
- One Telegram group has one active trip at a time.
- All commands operate on the active trip.
- The bot cannot fetch all Telegram group members automatically.
- Trip members are manually added by username.
- The payer of /add_expense is always the user who sent the command.
- Usernames after amount in /add_expense are split participants, not payer.
- If no usernames are provided in /add_expense, split among all active trip members.
- Multi-step sessions expire after 3 minutes (180 seconds). Do NOT change the TTL.
- When a session expires, send SESSION_EXPIRED message — never silently drop the reply.
- Multi-step sessions are scoped to the user who started the command (session key embeds user_id). Other users' replies are ignored.
- Settlements are stored as Expense(is_settlement=True), not a separate collection. They contribute to net balances but are excluded from total_spent.
- Use decimal-safe money calculations.
- Do not use floating-point arithmetic for money.
- Do not hardcode secrets.

## Commands

- /new_trip — create a new trip (multi-step: name, then members)
- /add_expense — add an expense; payer is always the sender; split participants are @usernames after the amount (or all members if omitted)
- /summary — show totals, per-member balances, and suggested settlements
- /settle — record a direct payment from one member to another (`/settle @username amount`)
- /delete_payment — soft-delete an expense by number
- /add_members — add @usernames to the active trip
- /delete_members — remove members from the active trip (multi-step)
- /switch_trip — switch the active trip
- /delete_trip — soft-delete a trip

## Development Guidelines

- Keep command handlers thin.
- Put business logic in services (`app/services/`).
- Put Firestore access in repositories (`app/repositories/`).
- Parsers live in `app/utils/parser.py`; user-facing strings live in `app/telegram/messages.py`.
- Register new commands in `app/telegram/webhook.py` (`COMMAND_HANDLERS`) and `app/telegram/commands_meta.py` (`BOT_COMMANDS`).
- Add tests for parsers, settlement calculation, session expiry, and command handlers.
- Mock at the service/repository layer in tests, not at the handler layer — `COMMAND_HANDLERS` captures function references at import time, so patching handlers directly does not intercept calls.
- Use `asyncio_mode = auto` (set in `pytest.ini`) — no `@pytest.mark.asyncio` needed.
- Use clear Telegram messages.
- Never silently fail.
- Prefer soft delete for trips, expenses, and members.

## Security Guidelines

- Verify Telegram webhook secret header.
- Store Telegram token in Secret Manager.
- Use Cloud Run service account for Firestore access.
- Do not commit .env or real credentials.
