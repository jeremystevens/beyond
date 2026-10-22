# Phase 40: first-run welcome guide

**Date:** 2026-10-21
**Status:** Implemented and locally verified. Owner review after a normal restart and fresh-machine acceptance remain pending.

## User experience

Fresh unconfigured installations and new successful Setup installations open /welcome from chat. Setup records pending welcome progress; a setup rerun does not lose it. Existing configured installations continue opening chat normally. Settings links back to the guide at any time.

The guide shows installed and currently available RAM, CPU thread count, the current model/connection, and three explicit CPU choices: Keep current, Lighter (up to four threads, 1024 context), Balanced (up to eight threads, 2048 context). Threads stay within the detected CPU count. Lighter/Balanced use f16 cache and disable thinking. Models, executable paths, network access and personal preferences stay as configured. External servers retain their own hardware configuration; only Keep current applies there. Selecting a preset requires applying it before testing.

Test my AI sends only a fixed greeting request, capped at 48 tokens, using the existing engine connector. It has a 90-second timeout, rejects busy engines and overlapping welcome actions, and never includes chats, memories, personality or house rules. Loading/failure/empty-response/timeout states support retry. Changed AI settings invalidate a test; a failed retest clears a previous success. A success is valid for the matching configuration for 24 hours.

Open chat requires that successful test. Set up later records an explicit skip and continues without claiming success. Progress lives in ignored data/welcome.json. Failed writes return actionable errors. Configuration, testing and completion require the same local-PC or signed-in administrator permissions as existing Settings; ordinary remote users see no host configuration or hardware details from the welcome endpoint. Model text and test replies render as text, not HTML.

Optional features remain a later Add-Features.cmd choice; the welcome page performs no installations or downloads. CPU is the supported path. Graphics-card testing is deferred until a compatible GPU backend exists, consistent with the CPU-only development-PC rule.

## Validation

- 76 targeted tests passed across welcome (20), sign-in/access, built-in engine lifecycle, text setup, optional setup and recovery. Tests used temporary data/settings and simulated AI responses; no actual AI model was loaded.
- Covered first-run detection, legacy installs, installer pending progress across reruns, completion/skip persistence, fixed prompt, failure/retry, empty reply, loading, timeout, busy/parallel operations, settings changes, CPU preset scope, unchanged external connections, expired/malformed progress and remote-device restrictions.
- JavaScript syntax checks passed for welcome.js and welcome-check.js; git diff whitespace validation passed.
- Headless Edge exercised the real page against a disposable loopback app with an AI stand-in: automatic welcome, Keep current, Lighter selection/application, failure then retry, short reply, unlocked Open chat, revisiting, skipping and no redirect loop. Mobile (390x844) and desktop (1280x900), light/dark mode, no horizontal overflow, and no page JavaScript errors. Screenshots were visually reviewed.
- The browser fixture uses a separate profile and disposable data, disables its GPU path, and closes only its own browser/server. Owner settings were compared before/after and unchanged. Live BEYOND, Local AI Studio, PromptetheusBot and connected work sessions were not restarted or stopped.

## Remaining acceptance

Jeremy can reopen the guide from Settings after his next normal BEYOND restart. Actual first-install walkthrough on a clean PC, no-Python bootstrap, and the pending pinned vision/DreamShaper inference checks remain Phase 42. These are deferred, not passed. The guide's AI test may contact an existing external AI server only when the user explicitly clicks Test my AI.
