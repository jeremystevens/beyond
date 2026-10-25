# Phase 52: Local error report preview/export (unreleased)

Final item in Jeremy's selected four-feature batch. Build useful local reports first; GitHub submission, duplicate matching and issue-status links remain future scope.

## Implementation

- Status and health → Recent errors → Report opens a dialog for what happened, expected behavior, reproduction steps and attempted fixes. Each optional field is bounded to 2,500 characters.
- Explicit Build preview reads one retained error category and optionally collects a few current local facts. No raw logs, chat reads, diagnosis/AI output, model names, addresses, credentials or identifying paths are collected. No AI call, external probe, upload or report-file write occurs.
- Fixed allowlisted descriptions replace arbitrary stored error text. Unknown categories get a generic summary. Optional facts include release/Python/OS versions, AI mode/state, feature switches, logical processors, RAM, free disk and uptime. Disabling facts avoids those settings/resource readings altogether.
- Best-effort redaction of common sensitive patterns in user notes precedes the editable preview. Review is still required; post-preview edits are copied/saved literally. Plain text is rendered via textarea values, never HTML.
- Copy and Save use exactly the visible preview. Save creates a client-side .txt download with a fixed filename. The browser controls its destination; notes/reports are not persisted by BEYOND. Editing notes/options invalidates export until rebuilt; rebuilding replaces preview edits. Close cancels outstanding requests; opening another report/reloading begins a new draft.
- Reports distinguish simulated test errors, and explain that current readings do not establish the cause of a historical failure. Missing/expired entries return an actionable error. Existing diagnostics/diagnosis remain separate.
- No new dependency, migration or version change. This phase implements the local-report part of brainstorm item 6, which stays partially complete until future GitHub integration.

## Validation

- Ten focused Python checks cover safe allowlists, optional facts, common redaction patterns, unknown categories/timestamps, simulated errors, expired IDs, validation, unavailable resources, literal text and no writes/side effects. Existing diagnostics and diagnosis tests also pass locally.
- Browser coverage exercises on-demand construction, notes/options, literal preview, exact edited Copy/Save, invalidation, expired-entry handling and mobile dark layout.
- Full Windows/browser CI and installed-app results will be recorded after execution. Follow docs/RELEASING.md before publishing; both release-version fields remain unchanged.
