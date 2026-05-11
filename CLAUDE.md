# CLAUDE.md

## Project Overview

This project is a Telegram group chat bot for trip expense splitting. It works like a lightweight Splitwise inside Telegram groups.

The bot lets users create trips, add members, add expenses, split expenses equally or partially, view summaries, and calculate simplified debt settlement.

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
- Multi-step sessions expire after 3 minutes.
- Use decimal-safe money calculations.
- Do not use floating-point arithmetic for money.
- Do not hardcode secrets.

## Required Commands

- /new_trip
- /add_expense
- /summary
- /delete_payment
- /add_members
- /delete_members
- /switch_trip
- /delete_trip

## Development Guidelines

- Keep command handlers thin.
- Put business logic in services.
- Put Firestore access in repositories.
- Add tests for parsers, settlement calculation, and timeout logic.
- Use clear Telegram messages.
- Never silently fail.
- Prefer soft delete for trips, expenses, and members.

## Security Guidelines

- Verify Telegram webhook secret header.
- Store Telegram token in Secret Manager.
- Use Cloud Run service account for Firestore access.
- Do not commit .env or real credentials.
