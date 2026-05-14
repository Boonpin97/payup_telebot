# TODO: Usability Commands

## Scope

Implement these commands:

- `/cancel`
- `/members`
- `/trips`
- `/expenses`
- `/edit_expense`

Do not implement:

- `/close_trip`
- `/settle`
- `/mark_settled`

## Decisions Locked

- `/cancel` can be used by anyone in the chat.
- `/expenses` is a text-only recent list.
- `/edit_expense` opens an expense picker first.
- No Firestore schema changes are required.
- Deleted trips and deleted expenses remain hidden.

## Implementation Tasks

- [x] Add new bot commands to `app/telegram/commands_meta.py`.
- [x] Register new command handlers in `app/telegram/webhook.py`.
- [x] Add `/cancel` handler.
- [x] Add `/members` handler.
- [x] Add `/trips` handler.
- [x] Add `/expenses` handler.
- [x] Add `/edit_expense` handler.
- [x] Add edit-expense picker callback action in `app/telegram/keyboards.py`.
- [x] Route edit-expense picker callback in `app/commands/callbacks.py`.
- [x] Reuse existing edit menu after an expense is picked.
- [x] Add message templates in `app/telegram/messages.py`.
- [x] Keep existing callback expiry behavior unchanged.

## Command Behavior

### `/cancel`

- If a chat input session exists, end it and reply: `Cancelled.`
- If no session exists, reply: `There is no active action to cancel.`
- Applies to sessions started by `/new_trip`, `/add_members`, `/delete_members`, `/add_expense`, and edit/partial split prompts.

### `/members`

- Requires active trip.
- Shows active trip name and active members.
- If no active trip, use existing `NO_ACTIVE_TRIP`.
- If no members, show `(none)`.

### `/trips`

- Lists all non-deleted trips in the group.
- Marks the active trip with `(active)`.
- If no trips exist, use existing empty trip message.

### `/expenses`

- Requires active trip.
- Shows newest 10 active expenses.
- Each item should include expense name, amount, and payer.
- If more than 10 expenses exist, append `...and N more`.
- If no expenses exist, reply with an empty-state message.

### `/edit_expense`

- Requires active trip.
- If no expenses exist, reply with an empty-state message.
- Otherwise show a vertical expense picker.
- Picking an expense opens the existing edit menu.
- Existing edit callbacks and text input handlers should remain the source of truth.

## Tests

- [x] Test `/cancel` with an active session.
- [x] Test `/cancel` with no active session.
- [x] Test cancelled sessions are no longer consumed by `inputs.maybe_handle`.
- [x] Test `/members` with no active trip.
- [x] Test `/members` with empty and populated member lists.
- [x] Test `/trips` with no trips.
- [x] Test `/trips` marks the active trip.
- [x] Test `/expenses` with no active trip.
- [x] Test `/expenses` with no expenses.
- [x] Test `/expenses` limits output to 10 and shows remaining count.
- [x] Test `/edit_expense` with no active trip.
- [x] Test `/edit_expense` with no expenses.
- [x] Test edit-expense picker opens existing edit menu.
- [x] Test expired edit-expense picker callback uses existing expiry handling.

## Verification

- [x] Run `pytest`. (44 passed)
- [x] Manually verify command list sync includes new commands. (setMyCommands runs on FastAPI startup; BOT_COMMANDS updated)
- [x] Manually verify `/command@botusername` still works in group chat. (`_parse_command` strips `@botname`; unchanged)
