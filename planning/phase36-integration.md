# Phase 36 integration notes

Status and health (0.36.2) follows the Phase 35 model-download work in commit
2c3335a7c4d29eda5e1b00e7fa6fae163aa5a96b.

## Integration

- The diagnostics router and lifecycle hooks sit alongside download recovery and shutdown.
- Settings links to Status and health; the chat header and hamburger layout stay as they are.
- /speed and /selftest use the shared command registry, keeping /help synchronized.
- Existing model browsing and download routes are preserved.

## Validation

Nine diagnostics and fourteen download checks passed with temporary data and stand-in services.
Seven diagnosis checks cover AI/basic fallback, concurrency, privacy, simulated-entry management
and low-memory warnings. Static checks cover Python/JavaScript syntax, HTML element references,
README formatting and Git whitespace.

After restart, the status and Models/download routes responded successfully, including /status
over HTTPS. Jeremy confirmed the live page and self-test work, tested the simulated error's
AI explanation, and verified the low-memory warning with 0.6 GiB available.

## Data and diagnosis

Diagnostic history retains at most 200 fixed summaries in data/diagnostics.sqlite3.
It excludes chat content and raw exception messages. Speed history reads saved reply statistics;
it does not benchmark the AI. Self-test checks services/settings/SQLite/files without running AI.

Diagnose sends the selected summary and allowlisted current health facts to the configured AI
server. Basic troubleshooting works when the AI is busy, unavailable or fails. It does not read
raw logs or conversations, start a model or perform repairs. One diagnosis runs at a time, with
a two-minute AI deadline. Results stay on the open page rather than becoming chat messages.

Add test error creates one labelled simulated timeout. Clear test errors removes only these
entries. Available RAM below 1 GiB warns on the resource card, in self-test and alongside AI
explanations, including for simulated errors. No automatic action is taken.
