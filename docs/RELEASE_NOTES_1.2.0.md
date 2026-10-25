# BEYOND 1.2.0

A feature release focused on everyday writing, returning to long chats, troubleshooting screenshots and reporting problems.

## What's new

- **Writing helper:** use the pen button or `/rewrite` alone to polish writing, reply to emails or draft documents. Includes 16 tones, audience/detail choices, technical/document formats, opt-in attached sources, revision, and draft-only Copy/Save.
- **Pick up where we left off:** Recap summarizes decisions, open questions and next steps on request. Unchanged chats reuse a private cache; ordinary replies never generate one. Long chats clearly disclose selected excerpts.
- **Screenshot troubleshooting:** attach, drop or paste an error screenshot and choose Troubleshoot this. Uses installed OCR first or optional CPU vision, then offers focused advice/questions. Evidence stays in recent chat context for follow-ups. No repair commands run automatically. Existing cached OCR models are supported.
- **Local error reports:** add notes, choose whether to include current system facts, preview/redact/edit, then Copy or Save exactly that report. Raw logs and chats are excluded. Automatic redaction is best effort: review before sharing.
- **Optional GitHub reporting and duplicate checks:** counts repeated local summaries, explicitly searches possible related public issues and shows open/closed links. Continue on GitHub opens the reviewed draft for your GitHub sign-in and final submission. No stored token or automatic issue creation. Long reports use Copy/paste. Simulated test errors stay local; offline/rate-limit checks are clearly marked. Matching text/categories do not prove the same cause.
- **Mobile composer:** full-width message box with quiet tool icons underneath.

## Updating

From a ZIP installation of **1.1.0**, use **Settings → Updates → Check for updates → Update to 1.2.0**. Git installations use `git pull` and restart. Older installations can use the bundled Update-Beyond.cmd in their BEYOND folder.

Your chats, memories, settings, models, files and optional features are kept. No new runtime dependency or database migration is needed. Python 3.14 and Windows 10/11 remain the setup target. Optional OCR/vision must already be installed or added through Add-Features.cmd.

Local preview/export makes no GitHub request. Checking GitHub is explicit and sends only a category/reference; Continue on GitHub sends the reviewed draft to the public issue form. Review reports for private information before continuing. GitHub search indexing and availability can limit duplicate detection.
