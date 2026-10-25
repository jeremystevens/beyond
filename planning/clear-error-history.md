# Clear recent error history

Status: implemented; unreleased after 1.2.0
Date: 2026-10-25

## Behavior
Settings → Status and health → Recent errors includes Clear error history.
The host PC or a signed-in administrator can confirm removal of all retained error summaries, including simulated entries.
Cancelling makes no request. A failed request keeps the list and explains the error.
Success refreshes the list and reports how many summaries were removed.
New errors are still recorded. Detailed logs, chats, settings and exported reports are preserved.
Clear test errors remains a separate action for simulated entries only.

## Compatibility
Existing diagnostics databases are migrated transactionally to automatically increasing IDs, preserving entries.
Clearing cannot reuse an old error ID and make an old report link refer to a new error.
DELETE /api/status/errors enforces host/administrator permissions on the server.

## Validation
- Twelve diagnostic tests passed on MSI, Windows/Python 3.14.
- Browser checks cover cancellation, request failure, successful clearing and non-admin visibility.
- Live updated markup/script and readable history were verified without clearing the user's history.
- User tested clearing and confirmed it works.
- Full Windows/Python 3.14 and Chromium CI must pass on the final commit before merge.
- Release version and phase remain unchanged.
