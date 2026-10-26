# BEYOND user guide

BEYOND is a personal AI assistant you run on your Windows PC. Start with text chat, then add voice or photo tools when you want them. Chat storage and built-in AI processing stay on your PC. Web lookups, downloads and any external AI server you choose use the network.

This guide describes the setup and welcome flow on the GitHub main branch. A separate-PC installation with existing Python and optional-feature tests passed by user report. Automatic Python installation on a PC without Python remains untested. GPU acceleration is not enabled.

## 1. What you need

- Windows 10 or 11 on an Intel/AMD 64-bit PC. Windows ARM and other operating systems are not supported by the automatic installer yet.
- Internet access for Python, libraries, engines and model downloads during setup.
- Room for Python, the environment, downloads, extracted engines and your chosen model. Setup checks free space on the installation drive.
- Available RAM for loading the model. Other applications reduce currently available RAM even when the PC has plenty installed. Setup offers Retry; you can cancel and return later without closing essential work.

Python **3.14, 64-bit** is required. You do not need to install it yourself: the beginner launcher offers a verified per-user installation. Existing Python versions are preserved. BEYOND uses its own .venv folder for libraries.

## 2. Download and install text chat

1. Open [jeremystevens/beyond on GitHub](https://github.com/jeremystevens/beyond).
2. For the current setup scripts, choose **Code → Download ZIP** from the main branch. Extract the ZIP completely to a folder you can write to, such as Documents/BEYOND. Do not run from inside the ZIP. Older release archives may not contain the current installers.
3. Double-click **Setup.cmd**. If BEYOND is already running, close it normally when convenient before changing its libraries. Local AI Studio and other bots can stay running.
4. Follow the Python and isolated-environment prompts. Setup verifies the official Python installer checksum and publisher before running it. It does not remove other Python versions.
5. Choose a chat model. **Qwen3 1.7B Q8_0** is the normal starting choice, about 1.71 GiB. **Qwen3 0.6B Q8_0**, about 610 MiB, is smaller and gives simpler answers. You can choose an existing GGUF file instead.
6. Approve the chosen downloads. Setup checks the files, installs a pinned CPU engine, and generates a short test reply. Settings are saved after successful verification. An existing external AI connection is kept unless you agree to switch.
7. Accept the desktop shortcut and open BEYOND if you want. A shortcut is optional; an existing shortcut is not overwritten.

If you already have Python, you can run `py setup.py`. It finds Python 3.14 or offers the beginner bootstrap when the required version is missing. The PowerShell alternative is `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1`; the override applies to that process only.

**Do not use `pip install beyond`.** The PyPI project named beyond is unrelated to this assistant.

## 3. Open BEYOND and complete the welcome guide

Use your BEYOND desktop shortcut. If you skipped it, open PowerShell in the extracted project folder and run:

```powershell
.\.venv\Scripts\python.exe .\beyond.py
```

BEYOND runs in the system tray. Double-click its icon or choose **Open BEYOND** from its tray menu. The default chat address is [http://127.0.0.1:7770](http://127.0.0.1:7770).

On a fresh installation the welcome guide shows the model, installed RAM and available RAM. Choose **Keep current** to reuse Setup's choices. **Lighter** reduces CPU threads and conversation context; **Balanced** uses a modest context with up to eight CPU threads. Apply a changed preset before testing. An existing AI server controls its own hardware settings.

Click **Test my AI**. BEYOND requests a short greeting using the current connection; it does not include your conversations or memories. Wait for a loading model, or retry after fixing a reported problem. A successful current-configuration test unlocks **Open chat**. **Set up later** continues without marking the test passed. You can reopen the guide from **Settings → Welcome guide**.

## 4. Your first conversation

Type a question and press Send. AI answers appear as they are generated. The same conversation provides context for follow-up questions. Start a new chat to change topics; previous chats remain in the sidebar and can be renamed, reopened or deleted.

Try:

- `Explain how a rainbow forms in three short sentences.`
- `/help` to see the available commands and examples. Typing `/` opens the same command list.
- `/remember my favorite color is blue` to explicitly save a memory.

Small starter models are useful for testing and basic chat, but can make factual or reasoning mistakes. A larger model may improve answers at the cost of more memory and processing time.

### Code answers (1.1.0)

Code in fenced blocks is displayed with preserved indentation and syntax highlighting for supported languages. Each block has **Copy code** and **Save code** controls in its header. Copy code copies only that block, without the surrounding explanation or Markdown fences. Save code downloads a text file with a suggested extension such as `.py`; your browser's download settings control the save location and whether a Save As dialog appears. The existing Copy button beneath an answer still copies the entire reply.

Controls become available when the reply finishes or is stopped. Reopened chats use the same formatting. If a model replies with unfenced code, ask it to put the example in a language-labeled code block. Unknown languages remain readable plain code. Downloading an example does not execute it; review generated code before running it.

### Adjust this answer (1.1.0)

Under the newest answer, press ✨ (**Adjust this answer**) and choose **Simpler**, **More detail**, **Show an example** or **Walk me through it**. Your choice appears as your message, and BEYOND answers it below. The original answer stays, so you can compare them. It's only offered on the newest answer; for an older one, ask in your own words.

### Local error reports

Open **Status and health** and find **Recent errors**. Press **Report** beside an entry. Optionally describe what happened, what you expected, steps to reproduce and what you tried. Each field allows 2,500 characters. **Include current app and system information** adds release/Python/OS versions, AI mode/state, feature switches, processor count, RAM, free disk and uptime. Turn it off to omit those current readings. The release version may not identify unreleased code from a git installation.

Press **Build preview**, then review and edit the report. **Copy report** copies exactly the preview; **Save report** downloads that same text as `beyond-error-report-<local error number>.txt`. The browser chooses the save location or asks where to save it according to your download settings. BEYOND does not write a report file into its installation, and it does not retain your notes as a saved draft. Closing/reopening or reloading starts a new draft. Changing the input notes/options disables export until you rebuild the preview; rebuilding replaces preview edits.

Reports use a fixed description for the recorded error category, not raw exception text. They do not automatically collect chat content, raw logs, diagnosis/AI output, user/host names, model names, file paths, server URLs or credentials. Common secrets, URLs, email/IP addresses and local paths in your notes are removed where recognized. This is best effort: review the text carefully before sharing, including any edits you make afterward. Preview edits are exported literally and are not redacted again.

No AI request, server reachability check, GitHub submission or upload is made by local report preparation/export. Current information describes the app now, not necessarily the moment of the error, and a fixed summary cannot establish the exact cause. Expired errors require refreshing and choosing a retained entry. **Add test error** provides a clearly marked simulated report for practice; **Clear test errors** removes only those test entries. Existing Diagnose/self-test features remain separate. **Optional GitHub reporting:** after reviewing the preview, press **Check GitHub for duplicates**. This sends only a fixed category and a hashed report reference to GitHub search, never the report body. Related open/closed issues appear as links. Matches are suggestions, not proof of the same cause; no matches does not guarantee a new issue (indexing can lag). The preview also counts identical summaries in retained local history without deleting or merging entries.

If an existing issue matches your problem, open it and add useful details there. Otherwise **Continue on GitHub** opens a prefilled issue in the main project repository. That explicit action sends the draft to GitHub; sign in and press GitHub's Submit button to publish it. BEYOND does not store tokens or create issues automatically. A long report may exceed the safe link size: Copy report first, continue, and paste it below the prefilled reference. Edits to the preview require another check before continuing. Offline/rate-limited searches are clearly marked; check issues manually before submitting. Simulated errors cannot be reported. Search results are cached briefly and include issue status; nothing is polled automatically.

### Screenshot troubleshooting

1. Attach a PNG, JPEG or WebP error screenshot using **+ → Attach photo or document**, drop it on chat, or paste an image into the message box. The existing limits apply: 10 MB, 25 megapixels, one still image at a time. Crop out private details before sharing it with BEYOND.
2. Optionally describe what triggered the error or what you already tried in the photo question field.
3. Press **Troubleshoot this**. **Automatic** uses installed **Read text in photos (OCR)** first, otherwise configured **Photo understanding (vision)**. Select **Read error text** to require OCR, or **Understand screen** to require vision for layout/icon problems. There is no silent download or switch to another reader after a failure. Use **Add-Features.cmd** to install the relevant reader; enable/configure Photo understanding in Settings for vision. You can also paste the exact error as normal text.
4. The job runs in the background. Its reply explains visible evidence, possible causes, up to three initial checks, and up to two focused questions. Reply normally with the result or missing details. The evidence and advice remain part of this chat's recent conversation context, including after reopening. As with other long chats, older messages can leave the model's context window.

The result includes the reader's bounded evidence so you can correct misread text. OCR cannot interpret layout, and vision can misread text or invent details; confirm important error codes and ask for clarification. An empty OCR result asks for a clearer crop, vision, or pasted text. The feature does not inspect your machine, run commands, make repairs, download programs, or verify a fix. It uses the configured text AI after the reader finishes; an external text AI receives that evidence if selected. The screenshot and messages are saved in this chat and removed when the chat is deleted. New troubleshooting evidence also invalidates its recap cache. Copy the answer using **Copy text**.

If a reader/model fails or is busy, BEYOND replaces the progress message with an explanation. The attached image remains available to try again while the page is open; after reopening, reattach it. Restart interrupts an unfinished job rather than silently repeating it. Existing Read text, Describe it, Receipt / totals and Ask a question actions continue to work separately.

### Conversation recaps

Open a saved chat and press **Recap** above the conversation to pick up where you left off. The recap covers the topic, user-confirmed decisions/agreed facts, unfinished questions and a suggested next step. Suggestions should remain distinct from actual decisions; review the result because a model can make mistakes. Attached file names provide context, but the recap does not read their full contents or check current web facts.

The first request generates a recap. Unchanged conversations reuse the saved recap without another model request, including after restarting BEYOND. **Refresh recap** explicitly generates another. New/edited messages, retried answers and added/removed attachments make the old cache ineligible; the next request creates a current recap. Opening chats and ordinary replies do not run recap generation.

For long chats, BEYOND sends bounded excerpts from the opening and recent messages so the request fits a small CPU model. The panel shows how many messages contributed and warns that older details may be missing. This is not a complete audit of every message. Very small/external context windows may require a larger context in Models or on the external server if the model rejects the request.

**Copy recap** copies the recap text. Close hides the panel; the cache remains in private **data/recaps/** until the chat is deleted. Deleting the chat removes its recap, and branches have independent caches. Keep recap files private with the rest of data/. A failed refresh leaves the existing cache intact; reopening can reuse it if the conversation has not changed. If the conversation changes during generation, BEYOND asks you to request it again rather than saving a stale result. A cache write failure still returns the generated text for copying. The configured AI connection handles the request, including an external server if selected.

### Writing helper

The **+** button, flexible message box and **Send** share one row on desktop and mobile. Open **+ → Writing helper**, or send `/rewrite` by itself. Attachments, voice and the thinking toggle share the compact + menu. Choose:

- **Polish my writing:** paste your text; optionally say what to change or preserve.
- **Reply to an email:** paste the incoming email and describe what your response should say. It creates a draft; it does not send email.
- **Draft a document:** supply notes/specifications or describe the document you need.

The tones are **Professional, Casual, Friendly, Technical and precise, Plain language, Formal, Diplomatic, Firm and assertive, Warm and empathetic, Persuasive, Instructional, Academic, and Concise and direct**. The existing **Funny, Polite and Dramatic** choices remain available too. Formal and casual are now separate tone choices. Existing shortcuts such as `pro`, `warm`, `kind` and `short` still work in the quick command.

Open **Audience and document options** to specify a reader (such as a customer, beginner, technician, developer or engineer), a detail level (overview/brief, practical detail, or comprehensive reference), and a document type. Types include a general document, letter, announcement, report, proposal, policy, technical specification, README, troubleshooting guide, installation guide, API reference, incident report, and tutorial/procedure.

For technical writing, paste the actual specifications, code or reference material. The helper is instructed to preserve numbers, units, versions and facts, use appropriate terminology, and mark missing details **[Needs confirmation]** instead of inventing them. Review every draft; model instructions cannot guarantee factual accuracy.

**Use documents attached to this chat** optionally adds relevant excerpts from existing attachments. It starts unchecked for a different chat. Long-document retrieval does not supply every page; for a complete long document, work on one section at a time. Paste up to 12,000 characters of source text. Combined source/draft/excerpt limits may require shorter sections, particularly with a small model.

Edit **Your draft** directly. **Copy draft** and **Save draft** use that text only; Save downloads `.txt`, or `README.md` for a README. Your browser controls the download folder/dialog. To revise, enter **What should change?** and press **Revise draft**; your edited draft is included in the next request. Errors and cancellation keep your source and previous draft. Drafts stay in page memory until refreshed/closed and are not automatically saved to chat or memories. The selected AI connection processes the text, just like other AI features; external servers receive it if configured.

For a quick edit without the helper, use `/rewrite <tone> <text>`, for example `/rewrite diplomatic I disagree with this approach.` or `/rewrite technical The device needs 12 volts.` `/help rewrite` lists every tone. Each draft or revision makes one model request. Ordinary chats do not incur an extra writing request.

### Attaching documents (1.1.0)

Choose **+ → Attach photo or document** beside the message box, or drop a file on the chat. Photos work as before. A **PDF**, **Word (.docx)** or **text/code** file (up to 20 MB) is attached to the chat, shown as "📎 Attached …" with a ✕, and listed at the top of the chat. With no chat open, a new one starts, named after the file. Every following question in that chat can use it; answers mention the page they used.

A small AI on a processor can't read a long document at once, so for longer documents BEYOND sends the parts that best match your question. Name what you're looking for ("the warranty", "page 9") for the best results. "Summarise this" covers the opening and headings, not every page. A chat can have up to 5 documents.

Only the text is kept, in BEYOND's database on your PC; the file itself isn't stored. Press ✕ to remove a document, or delete the chat. Scanned PDFs (pictures of pages) have no text: photograph a page and attach the photo instead. Password-protected PDFs and old .doc files can't be read; save a copy as an unprotected PDF or .docx.

### Branching a conversation (1.1.0)

Press ⑂ (**Branch from here**) under any answer. BEYOND makes a new chat with the conversation up to that answer and opens it, ready for your next message, and the original chat stays as it was. The branch is named after the original with "(branch)" (rename it with ✎), starts with a link back to the original, and has a ⑂ mark in the chat list. Each chat then goes its own way; deleting one doesn't delete the other.

### Recovering an interrupted reply (1.1.0)

If an AI reply fails or its connection ends unexpectedly, a small monochrome retry icon appears with the tooltip **Retry last prompt**. It starts a fresh answer to the same question, rather than continuing at the last generated character. Partial text remains visible. Reopening the chat also offers recovery for its latest incomplete turn. If BEYOND itself is stopped, restart it before retrying. Recovery does not repeat slash commands that could change files or other state.

## 5. Everyday tools and preferences

| Where to go | What it does |
|---|---|
| Settings | AI connection, chat prompt, persona, automatic lookups, memory, popups, startup and network options. |
| Models | List, download, load, unload and switch chat models; tune each model's CPU settings. Loading a larger model needs more available RAM. |
| Status and health | See available resources, connection checks, reply speeds and recent errors. Self-test checks configuration and existing services without generating an AI reply. |
| Search history | Browse saved lookup results independently of conversations, filter them, repeat a search or delete selected entries. |
| Games | Open the built-in games; `/games` and `/help` also show the choices. |

Use **House rules** for instructions that should apply across chats, or the **Chat prompt** editor for your own assistant instructions. Long prompts take a small CPU model longer to read. Automatic fact collection and old-conversation recall can be changed in Settings. Explicit saved memories can be managed with `/memories`.

Some tools work locally; web searches, weather, news and other online lookups contact their providers. An external AI server receives the prompts and context that BEYOND sends to it. Choose a local server or the built-in engine when you want AI inference to stay on your PC.

File reading, writing and editing are limited to BEYOND's files folder and require the host PC or administrator access. Review generated code and edits before running or relying on them. See `/help` and the [README feature reference](../README.md) for exact tool syntax.

## 6. Add optional features later

Close BEYOND normally, then double-click **Add-Features.cmd**. Select the individual features you want; review each model's size and terms before approving it. Other applications can stay open if memory permits. You may skip a failed selection and continue with the others.

| Feature | What gets added |
|---|---|
| Whisper | Local microphone transcription. Choose tiny for a smaller, faster start or base for generally better accuracy. Recording never downloads a model by itself. |
| Kokoro | Spoken replies. `/speak` or the optional automatic reading setting uses the installed local voice. |
| Piper | Another local speech engine or a fallback. The selected Ryan voice has its own noncommercial dataset terms; read the notice before installing. |
| OCR | Read text in photos with local recognition models. |
| Vision | Describe or ask about photos with `/look`. Installation and a photo test passed on the separate test PC. |
| Image generation | Generate pictures with `/imagine`. CPU generation can take several minutes; installation and generation passed on the separate test PC. |

Compatibility tests run on the CPU before activating newly selected settings. Already verified unchanged selections are skipped on rerun. Use `Add-Features.cmd --retest` to retest selected features. Adding Piper does not replace an already enabled Kokoro primary voice.

See [Third-party notices](../THIRD_PARTY_NOTICES.md) for the distinction between application, engine, package, model and voice terms. BEYOND's MIT license does not replace those terms.

## 7. Use a phone or another home-network device

BEYOND must remain running on the host PC. In **Settings → Sign-in**, set a password for other devices. Turn on **Allow other devices on my network**, save and restart BEYOND when convenient. Use the address shown by Settings from a device on that network; the loopback address 127.0.0.1 refers to each device itself.

Other devices normally sign in before using BEYOND. A separate administrator password lets a trusted device manage settings and host file paths. Ordinary signed-in users do not have that access.

Browser microphones require a secure page. Follow Settings' certificate instructions and use its HTTPS address for voice recording on other devices. Install a certificate only on devices you trust and control. This guide covers home-network access; it does not require exposing BEYOND's port to the public internet.

## 8. Stop, update and back up

Closing the browser tab leaves BEYOND running. Use the tray menu's **Quit BEYOND** to close the app and its own built-in engine. It does not close your other AI applications.

Before an update or backup, quit BEYOND normally when convenient. Keep a copy of **data/** (settings, conversations, memories and other local records), **files/** (your files), and any **models/** you want to preserve. Keep backups private: they can contain personal conversations and credentials. Optional models are large and can instead be downloaded again.

**Updating to a new version.** Open **Settings → Updates** and press **Check for updates**. When a newer version is out, press **Update to …**: BEYOND closes, a window shows the updater's progress, and BEYOND starts again on the new version. Your chats, memories, settings, models, files and optional features are kept, and if a step fails the previous version is put back. Turn on **Check for updates automatically** to be asked once a day with a popup. Only this PC or a device signed in as administrator can update. On 1.0.0, download `Update-Beyond.cmd` from the latest release page into your BEYOND folder (next to beyond.py) and double-click it once; later versions update from Settings.

If you installed with Git, update with `git pull` instead; or extract a newer ZIP separately. Keep your old folder and private data backup until the updated copy works. Run the newer Setup.cmd to prepare its environment; do not copy a .venv between folders or PCs. Engine/model settings may reference old absolute paths, so rerun setup or choose the new paths in Settings after moving folders. Avoid replacing your data with another person's data.

## 9. If something goes wrong

| Problem | Next step |
|---|---|
| Download interrupted | Reconnect and Retry. Completed verified downloads are reused and partial downloads resume where supported. |
| Low available memory | Retry later, choose the smaller chat model during setup, or use the Lighter preset. Essential apps can stay running. |
| AI still loading | Wait for the status to become ready before testing. Large CPU models can take time. |
| AI not reachable | Check the selected mode and connection in Settings. Use Status and health for the configured service checks. |
| Port already in use | The desktop shortcut shows an error dialog; console mode prints the same explanation. Stop the known test listener or another program only when safe. To keep that program running, change BEYOND's saved web_port as described below. |
| Optional feature failed | Retry or skip it. New feature settings are not activated until its test passes. Installed libraries are not rolled back automatically. |
| Invalid .venv | Preserve it by renaming it after closing BEYOND, then rerun Setup.cmd. Do not delete chats or models. |

Read-only checks from the project folder:

```powershell
.\Setup.cmd --check
.\Add-Features.cmd --check
```

See the [setup recovery guide](../planning/setup-recovery.md) for logs and detailed recovery. Logs and settings backups can contain private paths or settings: review and redact them before posting an issue. [GitHub issues](https://github.com/jeremystevens/beyond/issues) are for bug reports; the repository's [security policy](../SECURITY.md) covers security reports.

### Changing a port when BEYOND cannot start

With BEYOND closed, back up data/settings.json, then edit its web_port field to a permitted free port.
Preserve the other JSON fields and use a number, not quoted text. If the file does not exist, create a JSON
object containing that field. Do not change app/config.py to override a saved setting.
If network access is enabled, the next port is also needed for HTTPS. Launch again after saving.
When BEYOND is accessible, future port changes are available in Settings > Address and network.

For the Phase 42 conflict test, stop the temporary Python HTTP server with Ctrl+C in its own PowerShell
window, then launch BEYOND again. The application does not close that server or other programs itself.

### If automatic Python installation fails

Manually install official Python 3.14 (64-bit) from https://www.python.org/downloads/windows/, then rerun Setup.cmd. The launcher uses the same automatic bootstrap; it is not a separate workaround. Existing-compatible-Python setup passed on the test PC; the no-Python installation path remains untested.

### Quick host and model status

These commands are available on the development branch after 1.2.0; they are not in the published 1.2.0 ZIP.

- **/status** checks the computer running BEYOND, even when you chat from a phone. It reports CPU usage, RAM usage/available memory, free space on BEYOND's installation drive, system uptime, and AI connection/model state. Saved results are snapshots, not live widgets.
- NVIDIA GPU load, temperature and VRAM appear when `nvidia-smi` is already installed. Other or unavailable GPU metrics are labelled unavailable; nothing is installed and GPU acceleration is not enabled. The optional query has a two-second timeout.
- **/model** returns live engine/model information directly. You can also say or type **“What model are you running?”** or **“Which model is currently loaded?”**. After voice transcription these supported questions follow the same direct path, bypassing the LLM and its memories. Other wording may still go to the LLM.
- A ready built-in engine identifies its loaded model. An external server identifies its selected model; an unavailable/loading engine is not described as having a confirmed loaded model.
- Ordinary AI replies also receive built-in runtime state or a server-reported model observed within the last 60 seconds. Changing server settings invalidates that observation. Otherwise only the configured model is known, with its loaded state unconfirmed. This context helps the LLM but does not guarantee it will answer correctly; use **/model** for a direct check.

These checks generate no AI answer, load no model and restart nothing. Explicit server-model checks can contact your configured AI server (up to five seconds); ordinary replies add no network probes.

### Clear recent error history

In **Settings → Status and health → Recent errors**, **Clear error history** removes all retained summaries (including test entries) after confirmation. It is available on the host PC or to a signed-in administrator. This cannot be undone. New errors are still recorded; chats, settings, detailed log files and already exported reports are kept. **Clear test errors** continues to remove simulated entries only. This is an unreleased addition after 1.2.0.

### Check an answer against evidence

This is an unreleased addition after 1.2.0. Under a saved AI reply, open **Adjust answer** and choose **Check answer**. The original answer stays unchanged.

- **Calculator:** enter arithmetic or an equation such as `15% of 80 = 12`. Simple equations in the reply are suggested when recognized. This uses the safe calculator, without AI inference or network access; it checks that expression only.
- **Attached documents:** select one specific claim and compare it with passages from documents attached to this chat. File/page evidence appears alongside a separate AI assessment. Missing evidence does not prove a claim false.
- **Public web search:** enter the public query yourself, then press **Search and check**. Only that query is sent to search. Review the snippets and source links; pages are not opened, and search results are not proof that the whole answer is correct.

Checks are optional and add no requests to normal replies. One model assessment is used for document/web checks when available. If it fails, evidence remains available with no conclusion. Close to cancel; check results are not saved. Editing inputs hides the previous result. The dialog follows the current theme and fits narrow phones. See [implementation notes](../planning/answer-checking.md).

### Conversation working notes

This is an unreleased addition after 1.2.0. Open a saved chat and choose **Working notes**, beside **Recap**. Keep a short goal, confirmed facts, decisions and open questions there. Recap helps you catch up; active working notes are included as context for later AI replies.

Write notes yourself, or press **Draft from chat**, review and edit the result, then **Save and use**. Drafts are never used automatically. Saved active notes support later replies in that chat only; **Pause** keeps the text without using it, and **Clear notes** removes it. They are separate from global memories and do not add messages to the chat.

Notes are limited to 1,600 characters and refreshed on request. Normal replies add no extra model calls, but the small context block can add some prompt-processing time. The dialog tells you when there are newer messages. Drafting uses bounded excerpts in long chats and may miss older details; previous reviewed notes help preserve earlier context. Newer chat messages override old notes.

Editing or deleting covered history clears the notes to prevent stale facts. Deleting a chat deletes its notes; branches start with independent empty notes. If the chat changes during drafting or editing, reopen or draft again before saving. The dialog keeps unsaved text on errors. See [implementation notes](../planning/conversation-working-notes.md).

### Think it through and the + menu

This is an unreleased addition after 1.2.0. The **+** button beside the message box opens **Attach photo or document**, **Voice input**, **Writing helper**, and the **Think it through** checkbox. These tools use the same optional features and permissions as before. Active recording has a visible Stop recording control even when the popup is closed.

Turn on **Think it through** before asking a harder question. BEYOND drafts, critiques the draft for specific gaps, and revises with your current model, then streams the final answer. It takes longer; ordinary chat keeps its existing path while the mode is off. **Think it through: On** remains visible outside the menu; click it to turn the mode off. The preference is saved in this browser at this BEYOND address and stays on across chats until disabled.

For one question, use **/think <question>**, such as `/think Help me plan a small project with a limited budget`. This does not change the checkbox. **/think** alone shows help. Commands and dedicated tools keep their normal workflows. This is separate from the model's native-thinking setting in Settings.

Progress appears during preparation; intermediate text is not saved. Stop cancels the work, and Retry preserves the guided mode for a failed question. Planning and budget replies are instructed to check requested categories, practical essentials and totals, then show a brief **Final check**. Simple flat dollar-cost lists also receive a Python **Calculator check** of recognized items; ranges or nested costs may be skipped. Follow-ups can use the latest explicit budget in recent user messages, labelled as an earlier budget. Exactly matching named summary rows are excluded to avoid double-counting their components. Prices and completeness remain unverified. Estimates remain estimates. Multiple passes can still make mistakes and do not independently verify facts. Small-model testing still missed practical supplies and serving quantities; this optional mode is not a completeness guarantee. Further quality improvements are deferred. **Check answer** provides evidence checks. Guided mode uses bounded recent context and needs at least a 2,048-token built-in context; shorten oversized questions or choose a larger context. See [implementation notes](../planning/think-it-through.md).
