# Phase 49: Expanded rewrite and guided writing

Jeremy selected item 11 after reviewing the post-v1 brainstorm. This is unreleased feature work, not a release publication. Follow docs/RELEASING.md before changing app/config.py's version or root VERSION. Neither version is changed here.

## Included

- Preserve `/rewrite <tone> <text>` and existing shortcuts. `/rewrite` alone in the browser opens the helper, also available from a monochrome pen icon beside the composer.
- Thirteen requested tones: professional, casual, friendly, technical and precise, plain language, formal, diplomatic, firm/assertive, warm/empathetic, persuasive, instructional, academic, concise/direct. Retain funny, polite and dramatic for 16 total. Formal and casual now have distinct canonical styles.
- Three tasks: polish existing writing, reply to an incoming email with the user's stated intent, and draft a document from notes/instructions.
- Optional audience, brief/practical/comprehensive detail, and 13 document types: general document, letter, announcement, report, proposal, policy, specification, README, troubleshooting, installation, API reference, incident report, tutorial/procedure.
- Preserve supplied facts, numbers, units, versions and technical requirements. Use jargon appropriately for the audience; never invent specifications, credentials, references or test outcomes. Mark missing information for confirmation. These are model instructions, not a factual-accuracy guarantee.
- User-selected attached-document excerpts can inform drafts. Source/previous-draft text is data, separated from writing directions. Existing retrieval limitations apply.
- Editable output, revision using the user's current edits, Copy draft and Save draft (.txt; README.md for README). No email delivery, rich Word/PDF export, automatic host-file writes, or automatic conversation/memory saves.
- One configured-model call per action, bounded input/output, busy protection, request-disconnect cancellation, and source/draft retention on errors. No new model, runtime package, or database/settings schema change.

## Validation

- Local Python 3.12 checks: 11 focused tests cover all tones, aliases, quick-command compatibility, fact-preserving prompt construction, email intent, technical formats, revision, size/enum validation, opt-in sources, API schema, errors, cancellation and no chat/memory writes. Four existing prompt tests also pass.
- Browser regression added to the existing Chromium CI job: real page with isolated API/model stand-ins; all tone labels, email validation, technical/audience/detail controls, revision of edited text, exact draft Copy/Save, error/cancel preservation, optional attachments, safe literal text, phone width and dark mode.
- GitHub Windows Python 3.14/full-suite and browser CI must pass before considering the change ready. Record their results after running.
- MSI was offline during implementation. No live small-model quality/latency or Windows desktop smoke test is claimed. The code can be tested there after updating and restarting when the machine reconnects.

## Limits

Drafts are plain text/Markdown, not formatted .docx/PDF exports. Source text is bounded at 12,000 characters, previous drafts at 16,000, directions at 2,000, and combined context at 26,000. Small model context windows may require shorter sections. Long attached sources contribute selected excerpts, not their full contents. Drafts are held in page memory and disappear on refresh unless copied/downloaded. Automatic checks/updates remain governed by Phase 45; this feature does not publish or offer a new release.
