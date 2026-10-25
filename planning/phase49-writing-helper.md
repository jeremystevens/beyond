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
- Full GitHub Windows Python 3.14 and Chromium CI passed for b3790fb: https://github.com/jeremystevens/beyond/actions/runs/40155426689. PR #6 was integrated into main without changing either version field or the release signal.
- MSI reconnected after implementation. Its clean main checkout was fast-forwarded to b3790fb, and only BEYOND was restarted. The live writing-options API returned 16 tones and all three tasks; all 11 focused writing tests also passed on Windows there.
- Two short live model smoke checks passed: a professional email declined Monday and offered Tuesday; a technical specification retained 12 V DC, 2 A and firmware 2.4 and marked the missing operating temperature range for confirmation. These are basic functional checks, not comprehensive tone-quality, factual-accuracy or latency certification. Other bots and user data were left in place.

## Mobile composer follow-up

Jeremy found that the extra writing button squeezed the phone's message box. At widths up to 760 px, the textarea now has its own full-width row and attachment/microphone/writing controls sit beneath as monochrome icons with 44 px targets. Send/Stop is on the lower right. Desktop layout and existing event handlers stay in place. Windows Chrome browser checks passed at 320/390/760 px widths with a 440 px viewport height, alongside the full writing and code-block browser regressions. This is a CSS-only application change and does not require a backend restart or version change.

## Limits

Drafts are plain text/Markdown, not formatted .docx/PDF exports. Source text is bounded at 12,000 characters, previous drafts at 16,000, directions at 2,000, and combined context at 26,000. Small model context windows may require shorter sections. Long attached sources contribute selected excerpts, not their full contents. Drafts are held in page memory and disappear on refresh unless copied/downloaded. Automatic checks/updates remain governed by Phase 45; this feature does not publish or offer a new release.
