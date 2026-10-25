# Phase 53: GitHub reporting and duplicate checks · 1.2.0

Jeremy authorized both additions and a feature release. Reporting uses GitHub's own sign-in/final Submit action rather than storing tokens or requiring a registered OAuth app.

- Local report previews count identical source/summary entries within the retained 200-entry history, without deleting/merging records. Repeated summaries can have different causes.
- Explicit Check GitHub searches only the fixed main repository, using a stable hashed reference derived from category/problem/reproduction text, then a broader title/category fallback. The report body is never included in search. Bounded open/closed results exclude PRs and untrusted URLs; literal text rendering, short caching, busy/error/rate-limit and incomplete-search handling.
- After reviewing matches, Continue on GitHub opens a prefilled Markdown issue template. The user signs in and submits there. No token, automatic issue creation or claim that submission succeeded. Safe link-size limit falls back to a bounded reference/instruction body and Copy/paste for long drafts. Editing the preview invalidates the handoff. Simulated test errors cannot use online reporting.
- Search matches are possible duplicates only; indexing can lag. Hashes with generic/empty notes identify a category, not a proven common cause. No background checks or model calls.
- No new runtime dependencies, schema migration or persisted reports. 1.2.0 includes Phases 49–53 and the mobile composer improvement. Root VERSION remains 1.1.0 until assets are published and verified under docs/RELEASING.md.

Validation: focused backend and browser tests, full Windows CI, live read-only reporting checks and updater verification are recorded in release-1.2.0-validation.md.
