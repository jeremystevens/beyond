# Phase 50: Pick up where we left off (unreleased)

Selected by Jeremy after Phase 49. Add a recap on request and cache it until the conversation changes, without slowing ordinary replies with extra model requests.

## Implementation

- A small monochrome Recap button above a saved chat opens a dialog. It requests a cached/new recap; chat opening and normal replies only update button state and never call the recap API/model.
- One configured-model call for a new/explicitly refreshed recap. Ask for Topic, Decisions and agreed facts, Open questions, Suggested next step. Source messages are data; do not obey embedded instructions or treat assistant suggestions as user decisions. No chat/memory writes or web lookup.
- Read a consistent SQLite snapshot of message text/kind/stopped state and attachment metadata, without fetching images/audio/document bodies. A SHA-256 source digest makes edits, new/retried messages, and attachment changes invalidate cache reuse.
- Private JSON cache under data/recaps/, written atomically. No new database schema or runtime dependency. Delete alongside the chat; branches have independent cache paths. Failed model refresh preserves the old file, a changed/deleted source is not cached, and a cache write failure returns uncached text for copying.
- Bound transcript bytes and output according to the built-in context setting, or a conservative default for an external engine. Prefer the opening plus latest exchanges when the full history does not fit. Mark excerpts/omissions explicitly in the API and UI. This does not claim a full review of every historical message.
- Busy/duplicate requests are rejected rather than queued. Cached reads work without a ready model. Disconnect cancellation closes the model request. UI text is rendered literally, and results from a different chat are ignored.

## Validation

- 12 isolated Python tests: generation/cache reuse, source and attachment invalidation, busy/cache behavior, explicit refresh, concurrent edits/deletion, cleanup/independent caches, failed/empty outputs, malformed/unwritable cache, bounded Unicode excerpts and cancellation. Existing writing, branch, prompt and recovery regressions are also checked.
- Added browser coverage for no automatic recap on chat opening, generated/cached status, explicit refresh, coverage warnings, Copy, literal HTML safety, errors, switching chats, and mobile dark layout.
- Windows/full CI and live model smoke results will be recorded after running. Neither root VERSION nor app/config.py's release version is changed. Follow docs/RELEASING.md before publishing.

## Limits

Small models can omit/misinterpret details. Long histories use excerpts; a recap is not an exhaustive record and may omit older decisions. Attached document names are included, not their contents. Model context limits are estimated conservatively; an external model can still reject a request if its own configured window is smaller. Cached recaps are historical private data, not current facts or an independent source of truth.
