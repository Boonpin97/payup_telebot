"""Bot command list shown in the Telegram `/` slash menu.

Synced to Telegram via ``setMyCommands`` during FastAPI startup so the menu
always matches what the bot actually handles.
"""
from __future__ import annotations

BOT_COMMANDS: list[dict[str, str]] = [
    {"command": "new_trip", "description": "Create a new trip"},
    {"command": "add_expense", "description": "Add an expense to the active trip"},
    {"command": "edit_expense", "description": "Edit an existing expense"},
    {"command": "expenses", "description": "List recent expenses"},
    {"command": "summary", "description": "Show totals, balances and settlement"},
    {"command": "delete_payment", "description": "Delete an expense"},
    {"command": "members", "description": "Show members of the active trip"},
    {"command": "add_members", "description": "Add @usernames to the active trip"},
    {"command": "delete_members", "description": "Remove members from the active trip"},
    {"command": "trips", "description": "List all trips in this group"},
    {"command": "switch_trip", "description": "Switch the active trip"},
    {"command": "delete_trip", "description": "Delete a trip"},
    {"command": "cancel", "description": "Cancel the current action"},
    {"command": "help", "description": "Show bot info"},
]
