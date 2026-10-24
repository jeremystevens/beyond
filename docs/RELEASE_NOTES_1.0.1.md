# BEYOND v1.0.1 - Code blocks, Copy and Save

Status: release candidate; not published.

Code examples now appear in separate blocks with offline syntax highlighting. Each block offers Copy code and Save code, so explanatory text is not accidentally pasted into your editor. The existing bottom Copy action still copies the whole reply.

- Preserves indentation, line breaks and Unicode; multiple blocks have separate controls.
- Saves code with a suggested language extension, such as .py or .ps1. Your browser controls the download location and whether a Save As dialog appears.
- Works in reopened chats as well as new replies. Controls become available when generation finishes or is stopped.
- Common languages and PowerShell highlighting are bundled locally. Unknown languages remain plain code with working controls.
- Chat instructions now ask the model to use labeled code fences. If a model ignores that instruction, ask it explicitly to put the example in a fenced code block.

Failed or interrupted AI replies now offer a small monochrome retry icon with a Retry last prompt tooltip. Retrying starts a fresh answer to the same prompt, preserving partial text and conversation context without duplicating the prompt or recording negative feedback. Unexpected stream endings are detected instead of silently treated as complete. The latest incomplete turn can also be retried after reopening its chat.

No new Python packages, models, settings migration or database migration are required. Preserve your data, models and files when updating. Automatic updating is planned separately and is not included in this patch.

Existing setup limitations from v1.0.0 remain: automatic Python installation on a machine without Python has not been validated, and a fresh-PC Piper test remains unconfirmed. Manual Python 3.14 x64 installation followed by Setup.cmd remains the bootstrap fallback.
