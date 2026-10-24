# Phase 44: Code blocks, Copy and Save (v1.0.1 candidate)

Requested as an early high-priority improvement on 2026-10-23. Scoped separately from the larger post-v1 brainstorming and future release roadmap. Release is not published yet.

## Behavior

- Assistant fenced code becomes a labeled block with offline Highlight.js syntax colors.
- Each block has independent Copy code and Save code buttons. Source is kept separately from highlighted DOM, so labels, controls, surrounding prose and fences never enter the block payload.
- Downloads suggest code-N.ext using a controlled language mapping, falling back to .txt. Browser settings determine the folder and Save As behavior.
- The existing reply footer Copy still includes the entire original reply.
- User messages and prose stay plain text with safe http/https links. Code is displayed, never executed.
- Support backtick and tilde fences, longer enclosing fences, CRLF, indentation, Unicode, multiple blocks, and unfinished/stopped blocks.
- While streaming, code is shown without highlighting and controls are disabled. Completion or Stop highlights and enables the controls. Unknown languages, missing highlighting assets and blocks over 100,000 characters fall back to plain code.
- Default prompt and shared app contract request labeled fences. A model that ignores formatting instructions cannot reliably be reformatted by guessing; ask it to use a code block.

## Validation so far

- Four Node parser/filename regression tests passed locally and on Windows.
- Four Python prompt tests passed on Windows.
- Actual chat-page browser regression passed using isolated mocked API replies in installed Chrome on Windows: code-only copy, separate block download contents and extension, unchanged whole-reply copy, reopening via openChat, stream completion, stopped/partial blocks, HTML injection safety, clipboard fallback, and horizontal overflow on a phone-width viewport.
- Windows clipboard APIs normalize LF to CRLF; clipboard assertions allow that platform behavior while file-download assertions compare exact bytes.
- No live model request was made and no running bot was stopped. Live model formatting remains a manual smoke test.
- Initial code-block commit 18c12fc passed full Windows Python CI and Chromium CI (run 40052696772).
- Jeremy confirmed the code-block UI worked, then found failed generation lacked recovery. Added a quiet monochrome retry icon, a saved-question recovery route, retained partial answers without negative ratings or duplicate prompts, idle/EOF detection, and recovery on reopening incomplete chats.
- Five new backend recovery/engine EOF tests and extended browser tests for errors before/after tokens, abrupt EOF, inactivity timeout, quiet icon styling, and reopened incomplete turns passed on Windows. Existing built-in-engine, file-reading, and follow-up suites also passed.
- Recovery follow-up CI and live endpoint verification are tracked separately from the already-passed initial code-block run.

## Release scope

Application version candidate: 1.0.1; phase 44. No database/settings migration, runtime Python package change, model download, or automatic updater is included. Existing v1.0.0 installations need the changed application files; retain all data/models/files folders and the existing environment. A backup is recommended before any manual source update.

Before publication: CI passes, review final source diff and vendor checksums/licenses, prepare release notes/source archive with checksums, and retain the known v1.0.0 setup validation exceptions. Broader features and the updater stay in post-v1-feature-brainstorm.md.
