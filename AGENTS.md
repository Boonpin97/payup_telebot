# AGENTS.md

## Purpose

This file gives coding agents instructions for working on this repository.

## Project Type

Telegram bot backend deployed on Google Cloud Run using Docker and Firestore.

## Before Coding

Read:

1. README.md
2. CLAUDE.md
3. AGENTS.md
4. Existing tests

## Coding Standards

- Write modular code.
- Keep handlers small.
- Keep business logic testable.
- Avoid large files.
- Use type hints.
- Use consistent formatting.
- Add tests for new behaviour.
- Update README.md when setup changes.

## Firestore Rules

- Use repositories for database access.
- Do not access Firestore directly inside Telegram command handlers.
- Use transactions or batched writes for multi-document updates.
- Use soft delete where possible.

## Telegram Rules

- Every inline button callback must validate expiry.
- Every multi-step flow must create a session with expires_at.
- Every command must check active trip when required.
- Every invalid input must return a helpful message.

## Money Rules

- Store money in cents or Decimal.
- Never calculate money using float.
- Round consistently to 2 decimal places for display.

## Security Rules

- Never hardcode Telegram bot token.
- Never commit .env.
- Verify X-Telegram-Bot-Api-Secret-Token.
- Use environment variables or Secret Manager.

## Testing Requirements

Add or update tests for:

- Expense parsing
- Username parsing
- Equal split
- Amount split
- Percentage split
- Settlement simplification
- Member add/delete
- Session timeout
- Invalid input handling

## Deployment

The app must run in Docker and listen on the Cloud Run PORT environment variable.
