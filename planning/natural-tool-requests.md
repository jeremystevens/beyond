# Natural tool requests

Status: implemented; unreleased after 1.2.0.

The reported cat-fact and Tokyo-time requests lacked a route to their Python command. Existing weather/web/file/model handling did not cover them, and relevant prompt help omitted the small lookup modules. This was a routing/feature-help gap, not missing Python modules or lost saved memories.

app/natural_requests.py matches conservative whole-message requests to an allowlist of existing read-only commands. app/server.py calls it after explicit commands and pending file contents, before generic lookups/inference. Existing command handlers fetch or calculate the answer, save command-kind messages with the original user wording and return the normal stream. Typed and transcribed messages share this path. No model router, arbitrary command dispatch, new dependency or extra model pass is introduced. Existing tool-specific fallback behavior is retained.

Supported requests and limits are documented in README and the user guide. Feature help adds missing cat/quote/joke and catalogue information without putting every module into every prompt. General knowledge questions do not require current data unless the question actually needs it. Side effects retain their existing flows, and unrecognized wording falls back to chat or the slash-command alternative.

Tests cover polite spoken variants, the exact reported cat/Tokyo requests, fixed-clock time output, real command handler dispatch, no inference for supported direct commands, auto-lookup-off behavior, saved original wording, ordinary chat fallback, negation/quotes/multiple actions, unsafe/unsupported expressions, and pending-file precedence. Full Windows/Python 3.14 and Chromium CI passed on f484dc9. Live cat-fact and Tokyo-time smoke checks passed; the user verified improved behavior on mobile and approved this as a bug fix for the upcoming release. Release version and phase remain unchanged.

## Full tool audit
See [all 54 built-in commands](tool-routing-audit.md). A compact grouped inventory is generated from the live command registry for the stable system prompt; named command/alias usage is also generated from that registry. Tests cover every registered command and alias and fail if the audit omits a new command. Relevant UI feature help also covers Working notes, answer checking, code syntax checking and error reporting. There is no model routing pass. The extra inventory is a small stable prompt block, so it can reuse the existing engine prompt cache.
