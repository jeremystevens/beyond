# Changelog

All notable changes to BEYOND are recorded here, newest first.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.1] - Unreleased

### Added
- Conversation branches (Phase 47). ⑂ **Branch from here** under any AI answer makes a new chat with the conversation up to that answer and opens it, so you can try another direction while the original stays as it was. Branches are named "… (branch)", start with a note linking back to the original (or saying it was deleted), and have a ⑂ mark in the chat list. Ratings, older buttons, read-aloud audio and games stay with the original. Memory recall finds each exchange once, not once per copy. The database gains three columns (`chats.branched_from`, `chats.branched_at`, `messages.copied_from`), added at start-up; existing chats are unchanged.
- Adjust this answer (Phase 46). A ✨ button beside Try again, on the newest AI answer, opens **Simpler**, **More detail**, **Show an example** and **Walk me through it**. The choice is saved as your message ("Simpler, please"…) and answered below like any reply, so the original answer stays for comparison. It uses one normal reply (no extra AI call), never starts a web lookup or fact pickup, and the server accepts only those four choices for the newest answer.
- Easy updates (Phase 45). Settings → Updates shows the installed version and a **Check for updates** button; an optional daily check (off by default) offers a new version with a tray popup (Yes/No) and a dot on the Settings button. **Update to …** downloads the release's `Update-Beyond.ps1`, checks it against the release checksums, closes BEYOND and runs it: it backs up and swaps the program files, updates the libraries only when they changed, keeps data, models, files and the .venv, restarts BEYOND, and puts the old version back if any step fails. Only this PC or an administrator can check or update. Copies set up with git are told to run `git pull` instead. `Update-Beyond.cmd` updates a 1.0.0 installation once by hand, and `tools/make_release.py` builds every release file (ZIP with `app-files.txt`, updater, checksums, artifact.json).
- Quiet monochrome Retry last prompt controls for failed, timed-out, or unexpectedly disconnected AI replies, including failures before the first token. Saved prompts are reused without duplication or negative ratings; incomplete replies remain visible. Reopened chats offer recovery for their newest unfinished turn.
- Fenced code blocks with offline syntax highlighting, language labels, and independent Copy code and Save code controls. Each control uses only its own block's original code; downloads suggest a language-appropriate extension.
- Browser regression coverage for exact code downloads, code-only and whole-reply copying, reopened chats, streamed/stopped replies, safe HTML examples, clipboard fallback, and phone-width overflow.

### Changed
- Chat instructions request language-labeled code fences, preserving indentation and keeping explanations outside code blocks. Highlighting runs after streaming finishes; unknown languages and very large blocks remain plain code with working controls.
- Highlight.js 11.11.1 common languages and PowerShell are bundled locally with BSD-3-Clause notices. No runtime Python dependency, CDN request, database migration, or model download is required.

## [1.0.0] - 2026-10-22

### Documentation
- Recorded Phase 42 separate-PC results, including the corrected shortcut conflict test and user-confirmed
  Whisper/Kokoro/OCR/vision/image features. Prepared Phase 43 draft notes and release checklist.
  No-Python bootstrap remains explicitly untested; manual Python 3.14 x64 installation followed by Setup.cmd
  is the fallback. Application candidate version is 1.0.0; a GitHub draft does not publish the release.

### Fixed
- Windows recovery tests now confirm worker exit directly rather than relying on immediate disappearance of an exited process ID.
- **Phase 42 startup conflict:** desktop/tray launches now show a visible Windows error dialog when the
  web port is occupied; console launches retain the printed explanation. The tray's server starts only
  after the icon is ready, so an immediate startup failure can remove it reliably. Port guidance now points
  to the saved web_port setting and current Settings page instead of the obsolete Phase 4/config.py advice.

### Added
- **Phase 41 guide and notices:** new-user installation/use/recovery guide, third-party notice index,
  91-package version-matched inventory with 118 shipped notice texts, upstream license/model-card snapshots
  and provenance hashes, plus an offline notice collector. README links the guide and describes network
  behavior accurately. Name checks distinguish this GitHub project from the unrelated PyPI package.
  Piper's selected voice notice explicitly identifies RyanSpeech's noncommercial dataset terms.
  Tech Jarves acknowledgment is included; a courtesy message is prepared as an unsent draft.
  Fresh-machine acceptance and final binary-bundle notice review remain release follow-up work.
- **Phase 40 welcome guide:** fresh installs open a responsive guide that reuses Setup's model/connection,
  reports installed versus available RAM, offers explicit CPU presets, and tests a fixed short AI greeting.
  Finishing requires a successful current-configuration test; skipping is recorded separately. Existing
  configured installations continue to chat and can reopen the guide from Settings. Tests are bounded,
  reject concurrent requests and busy engines, and never include chats, memories or house rules.
  Manager permissions protect configuration and test endpoints. GPU testing remains unavailable; CPU stays
  the supported default. Fresh-machine and large-model acceptance remain Phase 42 work.
- **Phase 39E setup recovery:** interrupted HTTP transfers return to Retry with partial downloads preserved.
  Library installation and dependency checks use bounded, logged workers whose owned processes stop on
  cancellation or timeout. Invalid optional-feature numbers are rejected rather than partially accepted.
  Added a recovery guide and automated interrupted-transfer, rerun, timeout and cancellation checks.
  Fresh-PC/no-Python acceptance and pinned vision/image inference remain deferred to Phase 42.
- **Phase 39D optional setup preview:** Add-Features.cmd offers Whisper tiny/base, Kokoro, a separate Piper voice,
  OCR, vision and image generation. Selected assets use pinned sizes/checksums and license prompts. Optional
  libraries preserve text-runtime constraints. Each feature is checked in an offline CPU worker before its
  settings are saved; Retry/Skip and per-feature results keep independent selections moving. Windows job ownership
  closes native child processes on test cancellation/timeouts. Verified reruns skip unchanged selections.
  Whisper recording is now local-only, with an explicit model folder or an existing cached base model; OCR can use
  explicitly provisioned local files. Voice and OCR integration passed; full pinned vision/image inference remains
  pending on a PC with enough free memory.
- **Phase 39C text-only setup:** isolated text-library lock, pinned CPU llama.cpp and Qwen3 starter/fallback
  manifests, hardware preflight, model reuse, verified resumable downloads, app startup and real chat tests,
  memory Retry/lower-context options, settings backups, and optional shortcut/launch. Only the installer's own
  engine is stopped; existing external AI connections require agreement before switching. OCR no longer blocks
  a text-only app startup. Setup results and logs stay in data/setup. Optional feature installation is 39D.
- **Phase 39B setup bootstrap:** double-click Setup.cmd, use setup.ps1 without Python, or run setup.py with an
  existing Python 3.8+. Finds 64-bit Python 3.14, offers a per-user 3.14.8 installation after verifying the Python
  Software Foundation's Authenticode signature and pinned SHA-256, and creates or validates the isolated environment. Existing
  environments, other Python versions, PATH, settings, models and running apps are preserved. Read-only check,
  cancellation, download retry and plain-text branding fallback are included. The shared installer now continues
  into the Phase 39C text-chat installation.

## [0.38.4] - 2026-10-21

The first published release: everything from Phase 1 to Phase 38, plus the file tools.

### Added
- **Reading files** (version 0.38.4). Name a file from the files folder in a message ("what does animals.py do?",
  "read notes.md", "is there a bug in animals.py?", "summarise report.txt") or use `/readfile animals.py
  [question]`, and the AI reads it and explains it or answers the question. The page shows "📖 Reading
  animals.py…". The file stays open in that chat for up to six follow-ups ("and what does speak return?") or 30
  minutes; "thanks" closes it. Up to 12,000 characters are read (longer files say only the first part is shown),
  the contents are treated as data, not instructions, and the file is never changed or run. A question about a
  file never triggers a web search. Files that aren't text are explained as unreadable. This PC or an
  administrator only, like writing and editing.
- **Editing files** (version 0.38.3). "Add a speak method to animals.py" or `/editfile animals.py` with the changes
  (on the same line, the next lines or the next message) has the AI edit a file in the files folder. "Improve
  animals.py" (or "clean up", "refactor", "fix the bugs in") lets it use its own judgement: fixes, clarity and
  brief comments, keeping what the file does. With no changes given it asks, with a ✨ Use your judgement button.
  You see only the changed lines ("+" new, "-" removed) with **💾 Save changes**, **🔁 Change something else**
  (building on the draft) and **✖ Cancel**; "yes" saves too. Saving keeps the old version in
  `files/.versions/`, and **↩️ Undo** (or `/fileundo animals.py`) puts it back, one edit at a time. A file
  changed by something else meanwhile isn't overwritten, and Windows line endings are kept. `/filehelp` covers it.
- An edit or a new file starts only when you ask for one: the message has to begin with the action ("add…", "can
  you add…", "please improve…") and name a file that's there, and a new file needs "file" or "script" (or a type,
  as in "an html page"). Everyday messages like "add 5 and 7", "I'll add animals.py to GitHub later", "make a
  workout program" or "save it as a surprise" go to the AI as usual.
- **Asking for a file in plain words** (version 0.38.2). "Write a python file with a simple animal class" now works
  without a command. BEYOND works out the file type and what should be in it, and asks a short follow-up for
  whatever is missing: the kind of file (buttons for Python, Text, Markdown, JSON and HTML, or type any extension
  or name) or what to write. The AI then writes only the file's contents, and BEYOND shows them with a suggested
  name (animal.py) and **💾 Save**, **✏️ Different name**, **🔁 Change something** and **✖ Cancel**. "Yes", "save
  it", "call it pets" and "cancel" work too. Nothing is saved until you say so, and saving follows /writefile's
  rules (never overwrite: a taken name asks for another). "Save this as hello.py" saves the last answer as it is,
  without asking the AI again. A waiting request expires after 15 minutes, and /cancelwrite cancels it. This PC
  or an administrator only, like /writefile.
  - `/writefile test.py` followed by a description ("Write a simple python class for different animal types"),
    in the same message or the next one, now writes the code from it and shows the draft, instead of saving the
    description itself. Contents that read as real text or code are still saved exactly as sent.
  - `/filehelp` (also `/writehelp`) explains both ways to write files, with examples and a 📂 My files button.
- **/writefile, ported from PromptetheusBot** (version 0.38.1). `/writefile hello.py` followed by the contents on
  the next lines (or in your next message, within 10 minutes) saves a new UTF-8 text or code file in BEYOND's
  `files/` folder (git-ignored). Plain filenames with an extension only: no folders, paths or Windows device names.
  An existing file is never overwritten, nothing written is ever run, and files are at most 64 KB. The reply has a
  ⬇ Download button. `/files` lists them, newest first, with downloads; `/cancelwrite` cancels a waiting
  /writefile. The contents are never sent to the AI. Writing, listing and downloading files need this PC or a
  device signed in as administrator, even with sign-in switched off.

### Added
- **Phase 38: sign-in for other devices** (version 0.38.0). With "Allow other devices" on, a phone or another
  computer now signs in with BEYOND's password before it can open any page or use the API. The PC BEYOND runs on
  never signs in.
  - **Settings → Sign-in** (this PC only) sets, changes or removes the password (at least 8 characters) and lists
    the signed-in devices ("Chrome on Android · 192.168.1.50 · last used …"), each with Sign out, plus Sign out all.
    Changing or removing the password signs every device out. Another device sees "Sign out on this device".
  - With **no password set**, other devices can't use BEYOND at all and are told to set one on the PC, so turning
    network access on can't leave it open by accident.
  - **Administrator sign-in:** a second, different password lets a device (a phone, a work laptop) do what only
    this PC could: change Settings, download models, add file paths and manage sign-in. It's on the sign-in page
    as "Sign in as administrator", and in Settings → Sign-in on a signed-in device. Administrator sign-ins last up
    to 7 days. Each password signs out only the devices that used it when it changes. After a restart from
    another device, Settings comes back on that device's address instead of 127.0.0.1.
  - **Require other devices to sign in** (on by default) switches the whole feature off or on, saved straight away.
    Off, other devices open BEYOND without a password as before; this-PC-only settings and the refusal of requests
    from other websites still apply.
  - A **sign-in page** (`/login`) with "Keep me signed in on this device" (30 days, renewed while used; otherwise
    12 hours and gone when the browser closes). It returns you to the page you were opening. On the plain
    `http://` address it warns that the password isn't encrypted and links to the secure address.
  - **Safety:** only a salted scrypt hash of the password is stored, and only a SHA-256 of each session key, in
    `data/auth.json`. The session cookie is HttpOnly and SameSite=Lax (and Secure on https). Wrong passwords are
    slowed down per device after five tries, up to five minutes. Requests from other websites are refused. The
    sign-in page only returns you to BEYOND's own pages.
  - If a device's sign-in ends while a page is open (signed out, password changed or expired), the page goes to
    the sign-in page instead of showing errors.

### Added
- **Error diagnosis** (version 0.36.1). Recent errors now has a Diagnose button. BEYOND gathers current health
  evidence and asks the loaded AI for likely causes, evidence and suggested next steps, with a progress message.
  Basic troubleshooting remains available when the AI is busy, unavailable or fails; no model is started for it.
  Only fixed summaries and allowlisted health facts are sent to the configured AI server, without chat history,
  custom prompts, raw logs, credentials or file paths. One diagnosis runs at a time with a two-minute AI limit.
  No automatic repairs or settings changes are performed; results are shown on the page rather than saved in chat.
- **Simulated error for testing.** Add test error creates one clearly marked fake AI timeout without failing a
  service; Clear test errors removes only this category. Both controls and diagnosis results work on phones.
- Jeremy confirmed the Phase 36 Status page opens and all available self-test checks report ready.
  He also tested AI diagnosis with the simulated entry and confirmed the real low-memory warning is shown correctly.

- **Phase 35: model downloads** (version 0.35.0). The Models page can now download models from Hugging Face.
  - **Recommended models** for a processor (Qwen3 4B, Qwen3 1.7B, Llama 3.2 3B, Gemma 3 4B, Phi-4 mini, Qwen2.5 7B),
    each with its size, the memory it needs, what it's good at and a licence link. Their sizes and SHA-256
    fingerprints are pinned in `app/downloads.py`. A model you already have shows as **In Your models**.
  - **Any GGUF model on Hugging Face:** paste a link or `owner/name`, press Look up, and pick a file. Split models
    download every part as one item; vision projectors are left out. Fingerprints come from Hugging Face itself.
  - **Fingerprint checks:** each file is hashed as it arrives and only kept (renamed from `.part`) when its
    SHA-256 matches. A mismatch deletes it and says so.
  - **Resume:** a dropped connection is retried up to five times, continuing from the last byte with an HTTP Range
    request. Pause and Resume work the same way, and a download that was running when BEYOND closed waits with
    Resume. If a server ignores the resume request, the file starts again rather than being stitched wrongly.
  - **Free disk space** is checked before starting and before resuming, keeping 512 MB spare.
  - **Licences:** models whose terms the maker asks you to accept (Llama, Gemma, or any licence that isn't a common
    open one) need the tick box first. Gated models that need a Hugging Face sign-in are explained and linked, not
    downloaded.
  - Downloads go to `models/<owner>--<repo>/`, one at a time, with progress, speed and time left. A finished model
    appears in Your models straight away with **Load now**. Starting, pausing and cancelling are for the PC BEYOND
    runs on; other devices can watch progress. State is kept in `data/downloads.json`.

### Changed
- **Low-memory warning** (0.36.2): below 1 GiB available RAM is flagged on Status, in self-test and in Diagnose.
  Diagnosis shows a fixed warning and practical steps alongside the AI explanation, and tells the model to
  distinguish a simulated error from real resource pressure. No automatic repair or model change is performed.
- **A quieter line under each answer.** 👍 👎 🔄 and Read aloud were big rounded buttons on two rows. They're now
  small, light outline icons on one line under the answer (Copy, Good answer, Bad answer, Read aloud, Try again),
  with the stats on the right. The icons darken on hover, each one names itself on hover, and phones get bigger tap
  areas. **Copy** is new: it copies the answer's own words and shows a tick. The 👎 "what was wrong?" choices, game
  controls and downloads still show as normal buttons. Rating an answer no longer wipes its stats line until a reload.
- **Stats without bright emoji.** The model, tokens, time and speed (and thinking time) use thin grey outline icons
  that match the buttons: a box, two coins, a clock and a lightning bolt (a lightbulb for thinking).
- **Settings in a clearer order.** Sections are grouped, most-changed first, with jump links at the top: AI engine
  and models, Chat and everyday use (persona, house rules, chat prompt, spoken replies, memory, lookups, search
  history), Popups and startup, Photos and pictures, then Address and network. Nothing was removed. The Save bar now
  stays at the bottom of the screen while you scroll.
- **Faster cold first reply** (version 0.34.7). After a built-in model loads, BEYOND now pre-reads the stable
  system prompt with a one-token hidden request before reporting the engine Ready. This moves the cold prompt cost
  into startup instead of beginning it after the person presses Send. The warm-up is local, is never saved as a
  message, uses no user question, disables thinking, and does not run for external AI servers. If it fails, the
  healthy model remains available and the first chat processes the prompt normally. Owner verification reused
  the 740-token pre-read prefix, processed only 99 new prompt tokens in 3.7 seconds, generated 41 tokens in 5.1
  seconds, and completed the greeting in 8.78 seconds (shown as 9s).
- **Shorter chat prompt** (version 0.34.6). The default personality is now 257 words plus a 59-word app contract,
  about 85% shorter than the previous base prompt before memories and house rules. Broad tool instructions are
  attached only to relevant user turns. Saved memories, house rules, optional personas and the rule that replies
  cannot claim unfinished tool work still apply. This reduces prompt work on CPU models without promising a fixed
  response time; no automated AI timing benchmark or live chat playthrough was run.
- **Personas are optional and off by default** (0.34.5). Settings → Persona has a Use a persona switch,
  also saved by Save persona and the main Settings Save. Off omits every optional role block even if a
  non-Normal preset is saved. The saved preset remains available for later, and Reset to defaults turns it off.
- The narrow persona API accepts persona_enabled; phones can change the switch without general settings access.
  Existing settings without this field use off. The base personality, house rules and memories remain active.
- Investigated the reported first-answer delay through existing logs: the first request processed thousands of
  uncached prompt tokens, while later requests reused the prompt. Normal was selected and added zero role
  characters, so this does not demonstrate a persona-caused slowdown or a measured speedup from disabling it.
- README, personality and phase notes updated. A focused prompt check verified off for all five presets,
  explicit opt-in, saved preference persistence and retained rules/memories. Python/browser syntax, HTML IDs
  and whitespace checked. No automated AI timing benchmark or chat playthrough was run; owner comparison pending.


### Fixed
- **Looks things up instead of guessing about unfamiliar names.** "Have you ever heard of Omarchy Linux?" got a
  made-up answer, because automatic lookups only ran for current-events questions. Questions about a specific named
  thing ("have you heard of…", "do you know anything about…", "what is NixOS?", "who is Linus Torvalds?") now search
  the web first; general ones ("what is a fever?") still go straight to the AI. A correction like "you should always
  look up the information" now searches the last topic, and an answer that still sounds unsure gets a 🔎 Search the web
  for this button. The prompt also tells the AI to say it doesn't know a name rather than invent details.
- **Polite web-search follow-ups** (0.34.9). Normalize phrases such as “yes please”, “could you please”, “go ahead
  and” and trailing “for me” before routing explicit search requests. Extract the subject from “I was wondering
  if you know what Omarchy Linux is?” and skip an earlier missed search request when retrying. Regression checks
  cover the exact reported exchange, polite variants, negative requests, command invocation with stand-in results,
  progress, search history and no chat-model call. Owner playtest pending.
- **Web-search capability and natural requests** (0.34.8). Keep an explicit /web capability reminder in every chat
  prompt, including custom prompts. Replace the weather-only missing-information note with matching web/weather/news
  guidance so BEYOND does not claim the app lacks web access.
- “Search the web for <topic>” and same-chat requests such as “look it up” or “use the built in web feature” run
  the existing /web command in Python. Recent user messages identify the topic; AI guesses/denials do not.
  No prior successful lookup is required. An unclear topic asks for clarification, and explicit requests work
  with automatic lookups off. Existing progress, sources, search history and follow-up context are retained.
- Updated shared /web help, README and phase notes. Regression checks use temporary databases and stand-in search
  results for the reported Omarchy exchange, routing, isolation and negative requests; live playtesting stays with Jeremy.
- **Conversational weather requests** (version 0.34.4): keep a recent user weather request active while asking
  for the place, then run the real lookup when the user names it or confirms an unresolved request. Corrects
  the Franklin, Tennessee exchange where the AI repeatedly promised a search without running one.
- Explicit weather requests take priority over an old movie subject. Short confirmations use only recent user
  turns in that chat; unrelated topics and completed lookups do not trigger another search. Respects the
  automatic-lookups setting. Tightened the AI instructions against promising work after its reply ends.
- Recognize US state names/abbreviations without a comma, so “Franklin Tennessee” reaches the place finder as
  “Franklin, Tennessee”. README, personality and phase notes updated; owner recheck pending.
- Missing-comma handling now lives in the shared place finder, covering “Denver Colorado” and “Denver CO”
  across chat, /weather and /time. A failed weather location lookup accepts a corrected place in the next turn.
- Save pending weather requests per chat and message. Close US state typos offer a correction and confirmation
  button. Natural replies such as “yes thats what i want!!” run the actual lookup. Suggestions do not count as
  searches or silently change coordinates. Pending requests survive restarts and end after a new topic.
  Updated weather /help and per-answer instructions against promising future tool work; owner recheck pending.
- Seven focused checks passed with temporary databases and stand-in results, including the exact misspelled
  Franklin request followed by “yes thats what i want!!” calling the weather tool with no chat-model invocation.
  Pending-state persistence, chat isolation, new-topic boundaries and shared Denver geocoding are covered, along with
  state filtering, omitted commas, corrected locations, the exact reported
  exchange and the chat stream calling the weather tool, showing progress, saving context and recording one
  search without invoking the model. The live geocoder also resolved the suggested Franklin to Tennessee,
  United States. Python/browser syntax and whitespace checked.


### Added
- **Phase 36: Status and health** (version 0.36.0); integrated after Phase 35 and playtested by Jeremy. Settings links to a responsive page with CPU/memory/disk readings, bound service ports and reachability,
  model state, saved reply-speed history with per-model averages, recent error summaries, and a read-only self-test.
- **/speed** (optional 1–50 count) and **/selftest**, registered in shared /help and command discovery. Checks never
  generate an AI answer, load a model, install dependencies, download files, change settings or restart a service.
- Local bounded diagnostic error history (200 summaries), with no chat text or raw exception messages. Timings come
  from existing saved reply stats. Auto-refresh pauses while the page is hidden; optional disabled services are
  marked as skipped. README, API reference, context-aware feature help and phase plan updated.
- Validation: nine focused diagnostics checks passed, plus isolated ASGI routes/static assets/command discovery
  and self-test. Python/JavaScript syntax, HTML IDs, README formatting and whitespace passed. Combined download/diagnostics checks used temporary
  data and stand-in services. The live app was restarted and HTTP/HTTPS routes verified; Jeremy tested self-test,
  simulated-error diagnosis and the low-memory warning. Seven diagnosis regression checks also passed.
- **Custom chat prompts and AI optimization** (version 0.34.6). Settings → Chat prompt can use the optimized default
  or a user-written system prompt up to 16,000 characters, with a live word/character count, a prompt-only Save,
  default restoration and responsive phone/desktop controls. The optimized default is shown in the editor on a
  fresh install as a visible example. The custom prompt can be changed from home-network
  devices like persona and house rules; Reset to defaults clears it.
- **Improve & optimize** asks the loaded chat model to compress the editor text while preserving its intent. It shows
  elapsed progress, refuses while the model is busy, and returns an unsaved draft for review with Undo AI changes.
  It never changes saved settings until Save prompt is pressed and cannot add capabilities through the retained app
  contract. Four focused stand-in checks passed for persistence/default restoration, prompt limits, relevant tool
  notes, draft-only improvement, busy and failure paths. Python/browser syntax, HTML IDs and whitespace checked.
- **Natural lookup follow-ups** (version 0.34.3), added before Phase 35.
  - Successful manual and automatic lookups retain bounded source data and the subject in the current chat.
    “What about Paris?” after /weather London runs a new Paris forecast. Today/tomorrow questions refresh the
    current place, including a new place/day comparison. Clear comparisons also reuse news, wiki, define, movie
    and TV lookups; web/Stack Overflow comparisons ask whether to replace or extend the previous query.
  - Movie/TV follow-ups read available director, cast, runtime, year, ratings and plot from the lookup, naming
    the resolved title and source. Wikipedia lead director credits are supported. Missing facts are not guessed,
    and series-director questions ask about creators versus a specific episode.
  - Other short references can carry bounded, explicitly sourced context to the chat AI. They do not trigger an
    unresolved pronoun web search. Try again retains that context. Cached field answers need no model.
  - Context is isolated per chat, survives reload/restart, and is deleted with its chat. A new topic, unrelated
    command or failed lookup clears it; brief acknowledgments preserve it. History-page repeats establish
    context in their new chat. New network lookups enter search history once; cached facts do not.
  - Weather/movie command help and the styled README, personality and phase plan updated. Three focused checks
    passed using temporary databases and stand-in lookup results, covering routing, cached facts, chat isolation,
    retry context and deletion. Python/browser syntax, HTML IDs and whitespace checked; version 0.34.3 is serving
    over HTTP/HTTPS and the model loaded after restart. Jeremy completed the playtest and approved the feature
    on 2026-10-18.
- **Search history** (version 0.34.2), added before Phase 35.
  - Records web, Wikipedia, weather, news, Stack Overflow, dictionary, movie and TV lookup attempts, including
    command aliases and automatic web/weather/news lookups. Excludes jokes, quotes, cat facts, games and usage-only
    replies. Manual/automatic origin and success/no-results/error status stay with each entry.
  - Independent SQLite records retain UTC and local timestamps, timezone, query/tool, a bounded saved snapshot
    and source links. Deleting a chat leaves its history intact.
  - New /searchhistory (alias /searches), included in /help and command discovery, filters by date, tool or words.
    Explicit questions such as “What did I search for last Thursday?” route directly to real saved records, with
    five entries at a time and repeat buttons; no LLM is needed to recall history.
  - Settings → Search history opens a responsive page with date, query, tool and origin filters; Select all shown,
    checkboxes, selected-only deletion with confirmation, source links and Search again. Repeating fetches fresh
    results and creates a new history entry; page repeats open a new chat.
  - History starts with this update, has no automatic expiration, and is not injected into every chat prompt.
    Styled README, command help, phase plan and personality updated. Three focused temporary-database checks
    passed for chat-deletion independence, selected-only deletion, aliases/repeats, automatic lookups, literal
    filters and timezone/DST boundaries. Python/browser syntax, HTML IDs and documentation formatting checked;
    version 0.34.2, history/Settings pages, command discovery and the history API are available over HTTP/HTTPS.
    Owner playtest pending; no live searches or user-history deletions were performed.
- **Personas** (version 0.34.1), a small addition before Phase 35.
  - Settings → Persona offers Normal, Professional, Sarcastic, Evil and Funny, with a description for each style.
    Save persona applies just that choice; the main Settings Save includes it too. Normal is the default.
  - A selected preset adds role instructions to the chat system prompt. House rules, saved memories, honesty and
    task accuracy remain in place. One-off AI jobs retain their own instructions.
  - Applies to the next reply in existing and new chats without restarting BEYOND or reloading a model. The saved
    choice survives restarts; Reset to defaults returns to Normal. Answers already being written keep their prompt.
  - The responsive control works on phones and computers. Like house rules, persona can be changed from a
    home-network device through a narrow preset-only endpoint; general settings and host paths stay local-PC-only.
  - README styling retained; settings guide, API list, project tree, personality and phase plan updated.
    Python/browser syntax, HTML IDs, documentation formatting and whitespace checked; version 0.34.1 and all
    five preset choices are served over HTTP/HTTPS. Persona playtest pending; no automated chat/persona
    playthrough was run.
- **Phase 34: Models page** (version 0.34.0).
  - Models links from chat and Settings open a responsive page with file sizes, live loading status,
    load/unload/switch controls and a settings panel for each model. Cards stack on phones; names and paths wrap,
    and controls stay large enough to tap. On phones, Games and Models move into the hamburger drawer,
    leaving Settings and the AI status in a compact, single-row chat header.
  - Discovers GGUF files in BEYOND's git-ignored models folder and subfolders, groups split-model parts, skips
    vision projectors, and keeps the existing model visible without copying it. Existing files elsewhere can be
    added by path on the host PC.
  - Threads, context, cache and thinking are saved separately for each model in local settings. Listed models
    can be loaded and tuned from home-network devices; adding paths and configuring the executable stay local.
    Unload keeps the model off across restarts until Load is chosen again.
  - Chat cannot use a previous engine after a different model is selected. Model changes are refused during an
    AI request, and loading notices Unload or a different model without waiting for the full startup timeout.
  - Essential checks: three focused model-switch safeguards and the ten existing engine checks passed with
    temporary stand-ins. Python/browser syntax, HTML IDs and whitespace checked; Phase 34 page, model-list API
    and HTTPS serve successfully. Jeremy confirmed the Models feature works. His phone-layout feedback moved
    Games and Models into the hamburger menu; review of that revised layout is pending.
- **Answer stats:** a small line under every AI answer shows the model that wrote it, how long it thought (thinking
  models), the tokens written, the total time and the writing speed, e.g. `Qwen3-4B-Q4_K_M · 77 tokens · 36s ·
  2.10 t/s`. The numbers come from llama.cpp's own timings (or the server's token usage, or a count of the streamed
  pieces), are saved with the answer in a new `stats` column, and stay after a reload. Hover over one for what it means.
- **Phase 33: built-in engine** (version 0.33.0).
  - Settings → AI engine chooses between BEYOND's own engine and an AI server you already run. The built-in engine
    starts llama.cpp's `llama-server.exe` with your `.gguf` model on a free port only this PC can reach, waits for
    `/health`, and is used by every chat, command and lookup exactly like an outside server.
  - Tuned for a processor-only PC: 12 threads, 8192 context, f16 cache (flash attention only for a q8_0/q4_0 cache),
    one conversation slot so the prompt cache keeps working, no layers on a graphics card, and thinking models (Qwen3)
    answer straight away with thinking switched off unless "Let thinking models think first" is on (then the
    thinking is kept out of the answer). All of these are in Settings.
  - With thinking on, the answer bubble shows **💭 Thinking… 12s** with a running timer while the model thinks; how
    long it thought appears in the answer's stats line. The thinking itself is never shown or
    saved. Thinking gets 2000 tokens of its own on top of the answer's limit, and one-off jobs (fact pickup,
    `/rewrite`, `/joke`, the study quiz, the picture prompt helper) never think, so their small limits still fit.
  - A watcher keeps the engine in step with the settings: saving new ones restarts it, switching to an AI server
    stops it, and if it stops by itself it's started again (three tries, then **Restart engine** in Settings). A
    leftover engine from a crash is stopped on the next start, and quitting BEYOND frees the model's memory. The
    engine's own output goes to `data\engine.log`.
  - The chat page shows "AI engine starting…" while the model loads and "AI engine stopped" if it fails; a popup says
    so too. Fresh installs default to the built-in engine; setups that already had an AI server address keep using it.
- **Phase 32: hangman** (version 0.32.0), ported from PromptetheusBot.
  - `/hangman` opens a picker with difficulty (Easy 4–6, Medium 7–9, Hard 10+ letters) and five categories;
    `/hangman animals medium` starts directly. The round shows a gallows drawing that gains a body part on each
    miss, the word with blanks, and an A–Z keyboard (also usable by typing) that colours hits and misses. One free
    hint per round; Play again, Change category, Stats and Games follow every round; `/hangman stats` shows wins,
    losses, win rate and streaks. The Games menu now has every game ready.
  - The bot's word bank (about 260 words with hints) and rules are unchanged. Rounds are saved like blackjack hands:
    the word and an unused hint stay in `hangman_rounds` on the server, guesses carry a revision so stale or repeated
    clicks can't count twice, and a finished round counts once in the record and the shared game stats.
- **Phase 31: blackjack** (version 0.31.0), ported from PromptetheusBot.
  - `/blackjack` (alias `/bj`) deals a hand on a card table in the chat: real-looking cards, the dealer's hidden card
    as a card back, Hit and Stand, then the dealer plays to 17 (standing on soft 17). Naturals end the hand on the
    deal with an explanation. Deal again, Stats, Rules and Games follow every hand, and the Games menu has a
    Play blackjack button. `/blackjack stats` and `/blackjack rules` work as in the bot.
  - The rules are the bot's, unchanged (`app/tools/blackjack.py`). Hands are saved like trivia rounds: the deck
    and the face-down card live in `blackjack_hands` on the server, and the chat message only holds the face-up
    cards. Moves carry a revision, so a stale or repeated click can't change a hand twice, and a finished hand
    counts once in both the blackjack record and the shared game stats. Hands refresh across devices.
- **Phase 30: study quiz** (version 0.30.0), ported from PromptetheusBot's /quizme (one user).
  - New `app/study_quiz.py`: offline math questions (addition, subtraction, multiplication, division,
    percentages, squares, mixed math, times tables) with exact answers and worked explanations, and AI-written
    multiple-choice questions for any other topic (with one retry for malformed replies, and a prompt that
    forbids a second correct choice). Levels 1–5 per topic (3 right in a row up, 2 wrong down), saved in
    `quiz_progress`; each answer is also counted in the shared game stats.
  - **/quizme** (alias /quiz): topic buttons, four answer buttons per question (math wrong answers are typical
    slips), Skip, Stop, **Next question ▶**, `/quizme stats`, `/quizme stop`. One quiz at a time, shared across
    chats and devices, ending after 15 idle minutes. An old question's buttons can't be answered twice.
  - Buttons can now **send a command** as if typed (`{"label", "send"}`), used for Next question and the topic
    picker. The Games menu's Study quiz card is ready, with **Start a quiz**.
  - Tested: every math topic and level (four distinct choices including the right answer, worked out
    independently), level up/down and limits, answer/skip/stop and stale questions, idle expiry, AI question retry
    and failure, a full play-through over the API (including no AI server), a live AI topic, and the page in the
    browser (menu card, topic buttons, answering, Next question). 9 new tests; all tests pass.
- **Phase 29: trivia** (version 0.29.0).
  - Added /trivia, category/difficulty pickers, four answer buttons, feedback, Next question and round totals.
    Up to five questions are fetched together, with Play again, filter changes and saved scores.
  - Ported the bot's categories/aliases, Open Trivia DB/The Trivia API fallback and Easy/Medium/Hard 1/2/3
    scoring, accuracy and streak rules. Added bounded source requests, batch caching, validation and credits.
  - Private answer keys/future questions stay off the browser. Rounds survive reload/restart, and answer,
    progress and shared/local scores commit together. Stale/duplicate clicks cannot score twice.
  - Updated /help, command discovery, Games, README, personality and phase plan. Phase 28 owner test passed.
  - Verification: all 111 tests passed, including 15 trivia checks for filtering/aliases, source decoding,
    bounded HTTP, fallback/cache/validation, complete-round points/accuracy/streaks, private answers, duplicate
    and stale submissions, rollback, deletion, reloads and concurrent chat while fetching. Both question services
    returned valid live questions. Chrome completed a live five-question round with correct/wrong feedback,
    4/5 scoring, Next, source credits, device refresh, reload, disconnect retry, saved filters, draft preservation
    and mobile/desktop layouts. HTTP/HTTPS and active-round/score persistence after restart passed.
    Declared Requests explicitly (already pinned in the lockfile). Python/browser syntax, dependencies and
    whitespace checked. Owner tested Phase 29 and confirmed it works well on 2026-10-18.


- **Phase 28: tic-tac-toe** (version 0.28.0).
  - Added /tictactoe (/ttt), a difficulty picker and a real clickable 3×3 board accessible from Games.
  - Ported the bot's Easy, Normal and Impossible move rules unchanged. Winning lines, clear results,
    occupied/finished cells, New game, Change difficulty and game records are rendered for the browser.
  - Boards stay in chat and resume after reload/restart. Visible boards refresh across devices; revision
    checks reject stale or duplicate clicks. A board and both per-difficulty/aggregate stats commit together.
  - Completed games count exactly once; wins/losses/draws are shared across chats and retained after deletion.
    Existing saved Games menus reflect newly available games.
  - Updated shared /help and browser discovery, README, personality and phase plan. Phase 27 owner test passed.
  - Verification: all 96 tests passed, including 13 new tic-tac-toe checks. Full Easy/Normal games cover
    wins, losses and draws; Impossible covers BEYOND wins/draws and exhaustive play confirms it never loses.
    Duplicate final moves, stale/occupied cells, request validation, atomic rollback, deletion and saved boards passed.
    The five rule functions match the bot source exactly. Chrome completed Easy/Normal wins and an Impossible
    draw, checking winning lines, second-device refresh, reload, disconnect retry, new games, chat availability,
    draft preservation and phone/desktop layout. Live HTTP/HTTPS and board/stats persistence after restart passed.
    Python/browser syntax, dependency consistency and whitespace checks passed. Owner play check pending.


- **Download certificate** (Settings), so other devices can trust BEYOND's secure address and skip the browser
  warning for good (owner's request).
  - `app/https.py` now makes BEYOND's own small certificate authority (EC P-256, 10 years, CA with path length 0,
    critical name constraints: home-network ranges and this PC's name) and signs the server certificate with it.
    The server certificate is still renewed automatically (new addresses, near expiry, or a new authority); the
    authority stays, so devices that installed it keep trusting BEYOND. Only home-network addresses go in the
    server certificate (a VPN address would break the constraints). The old self-signed certificate is replaced
    automatically.
  - `GET /api/https/certificate` serves the authority's public certificate as `BEYOND-certificate.crt` (only while
    the secure address is on). Settings shows **⬇ Download certificate** with install steps for Windows, Android,
    iPhone/iPad and Mac; the 🎤 message on plain-http pages points to it.
  - Tested: the download from another address over http and https; trusting only the downloaded file (OpenSSL,
    strict), BEYOND's secure address is accepted by IP, by the PC's name and on 127.0.0.1, and a wrong name is
    rejected; 7 HTTPS tests, including the authority outliving a server renewal and a forged certificate for a real
    website (and for a public address) being rejected by the name constraints. The owner installed it on
    another PC and the browser warning is gone (2026-10-18).
- **Phase 27: games menu and dice** (version 0.27.0).
  - Added /games, /games stats and a Games header button that preserves message drafts and attached photos.
    The menu offers quick dice/coin rolls and marks later games with their planned phases.
  - /roll now supplies saved visual dice/coin results from the same secure server roll as the original text,
    including keep/drop markings, repeats and totals. Roll again creates a new result; reloads reuse the saved one.
  - Added shared local score/stat storage for completed plays, exact integer scores, best scores and win/loss/draw
    outcomes. Dice/coin stats work across chats and survive chat deletion; concurrent updates are transactional.
  - Preserved the existing dice notation and limits. Large modifiers keep exact totals; visual results cap at
    60 dice while retaining the full text. Games stay outside the AI's conversation context.
  - Updated shared /help and command discovery, README, personality and phase plan.
  - Verification: all 80 tests passed (13 games/dice tests plus 67 existing regressions), including one-roll
    display accuracy, notation/limits, saved rerolls, stats after chat deletion, concurrent score updates and
    exact large totals. Chrome checked quick rolls, coin flips, keep/drop visuals, saved reloads, stats,
    draft preservation, visible play controls, the 60-die display cap, and mobile/desktop layouts.
    Live HTTP/HTTPS and restart persistence passed; Python/browser syntax, dependencies and whitespace checked.
    Owner play check pending.


- **A secure address for other devices** (Phase 26 follow-up, owner's report: 🎤 didn't work from another PC).
  Browsers only allow the microphone on https:// pages or on the PC itself. With network access on, `beyond.py`
  now also serves BEYOND over HTTPS on the next port (7771), next to the usual http://…:7770.
  - New `app/https.py`: BEYOND's own self-signed certificate (EC P-256, 397 days, not a CA) covering this PC's
    network addresses, its name, 127.0.0.1 and localhost; stored in `data/https/` and made again when the
    addresses change, it nears expiry, or the files are unreadable. New dependency: `cryptography`.
  - The second server runs without its own startup jobs (`lifespan='off'`), so reminders, the briefing and the AI
    watch still run once; it stops together with the main one (Quit, restarts after settings changes). If the port
    is busy or the certificate can't be made, BEYOND carries on over http only and says why.
  - `/api/health` reports `https_port`. On a plain-http page from another device, 🎤 now offers the secure link
    (keeping the open chat) with a note about the one-time browser warning; Settings lists the https:// addresses.
  - Tested: health, the page and voice input over https://192.168.50.22:7771; the certificate's names; a reminder
    going off exactly once with both servers; 4 new tests (names covered, reuse, renewal for a new address,
    unreadable files, both servers stopping together); all 67 tests pass.
- **Phase 26: voice input** (version 0.26.0).
  - A **🎤 button** beside the message box: tap, speak, tap ⏹. The browser records (WebM/Opus in Chrome and Edge,
    MP4 in Safari), BEYOND turns it into text and the page sends it like a typed message. States: 🎤 → ⏹
    (recording, red) → ⏳ (working). Stops by itself after two minutes; text already typed is kept in front.
  - New `app/tools/speech_to_text.py`: faster-whisper "base" on the processor (int8, beam 5, voice-activity
    filter), ported from PromptetheusBot's voice notes. One recording at a time; the recording is written to a
    temporary file for the decoder and deleted at once. New endpoint `POST /api/transcribe` (raw audio, at most
    10 MB) returns the words or a plain-words error (empty, too long, unreadable, no words heard, busy).
  - Where the browser doesn't allow the microphone (plain http from another device, or no recording support) the
    button is greyed out and explains why. Denied permission and a missing microphone have their own messages.
  - New dependency: `faster-whisper` (with `ctranslate2` and `av`). The model is downloaded once (about 145 MB).
  - Tested: a spoken question as WAV and as WebM/Opus ("What is the capital of France?", exact, in under 2
    seconds each), an empty, an unreadable and an oversized upload, two recordings at once, and the whole page flow
    in the browser (the recorded question went through 🎤 → ⏹ → ⏳ → sent, and got a normal answer).
- **Phase 25: spoken replies** (version 0.25.0).
  - Added /speak for the last AI answer or supplied text, Read aloud buttons, and optional automatic reading
    of completed answers. The shared registry updates /help, /help speak and browser command discovery.
  - Added saved browser audio players with playback/seek controls, progress, retry and reload persistence.
  - Ported local Kokoro speech with Piper fallback into isolated, bounded CPU workers; one clip runs at a time
    with a four-request queue. Interrupted requests recover to a retryable state; chat remains available.
  - Added host-only speech settings for engine, voice files, speed, CPU threads and timeout. Automatic reading
    defaults off. Long answers are bounded to 1800 cleaned characters with a visible truncation notice.
  - Updated README, personality, phase plan and dependency pins. Real Kokoro, Piper and forced fallback
    generated valid PCM audio on the owner's CPU.
  - Verification: 41 existing regression checks and 15 speech checks passed, covering CPU-only sessions,
    fallback, literal subprocess input, bounded/deduplicated queues, concurrent chat, automatic reading, saved
    clips/ranges/deletion, retry and shutdown/restart recovery. Chrome verified actual decoded playback,
    automatic playback, reopening saved clips, navigation pause, repeat-error retry controls and mobile layout.
    Python/browser syntax, dependency consistency and whitespace checks passed. Owner listening check pending.


- **Phase 24: better pictures** (version 0.24.0).
  - Added Improve prompt to /imagine: the existing chat AI expands an idea while preserving requested subjects,
    colors, styles and exclusions. Review/edit and Undo improvement keep the person in control before generating.
  - The helper is asynchronous, bounded to one minute, leaves the original intact on error, and ignores late
    results after cancellation/navigation. Generating directly still works when the chat AI is unavailable.
  - Picture generation now always passes automatic negative prompts to the CPU worker: common quality/anatomy
    defects, with explicit monochrome/coloring-book handling and lettering-aware text avoidance.
  - Saved requests include the actual avoid words. Added a bounded optional API seed for controlled comparisons;
    ordinary browser generations remain random and use Quick / Good / Best.
  - Updated /help imagine, browser command discovery, README, settings guidance, personality and phase plan.
  - Verification: all 41 checks passed, including the existing scan/vision/image regression suite, helper
    validation, timeout cancellation, style/visibility guards, negative CLI arguments, saved requests and seeds.
    Chrome mobile checks passed for review/undo, offline fallback, cancellation, stale replies, chat controls
    and submitting the manually edited idea. Python/browser syntax, dependencies and whitespace checked.
    Live AI preserved coloring-book/no-shading and red/blue cartoon requests. Original vs improved cat-in-space
    pictures were saved/downloaded at 384px with Good and seed 42 in chat 86. The final
    improved render took 222.6 seconds. Owner visual-quality/UI review remains pending.
  - Live trials exposed unsolicited color bans and an underlit rewrite. Tightened instructions, rejected
    unrequested monochrome changes, shortened suggestions, and kept the original idea first with readable
    subject guidance. Outline art and explicitly dark requests keep their intended style.
- **Phase 23: /imagine** (version 0.23.0).
  - Ported the bot's CPU DreamShaper worker into BEYOND. Quick / Good / Best presets use 256px/8, 384px/12
    and 512px/15, with honest approximate times of 1–2, 3–5 and 9–12 minutes.
  - Browser prompt editor and preset buttons start a background job; chat, navigation and browser closure remain
    usable. One picture at a time, saved progress, independent CPU process at below-normal Windows priority.
  - Finished pictures persist in their chat with Download PNG, including after reload and on network devices.
    Picture prompts/results are excluded from text-model history and recall. Deleting the chat discards in-flight
    results, removes saved pictures and clears popup preview files.
  - Shared completion notifications support a small image preview with a text-only fallback, preserving all
    existing popup preferences, quiet hours, pause and page-presence behavior.
  - Added host-only picture settings with clean disabled defaults and empty owner paths; configurable threads
    and a 20-minute timeout. Process cancellation/reaping, output validation, temporary cleanup and restart
    recovery prevent abandoned progress. No new dependencies; Studio and the bot are unchanged.
  - Updated /help, /help imagine, the browser menu, README, personality and phase plan.
  - Verification: all 30 tests pass in one run, including real OCR. Live app: Quick 118.4s, Good 236.4s, Best 609.3s.
    Every preset produced a PNG at its expected size; saved progress was replaced and downloads worked.
    Text chat replied during generation, health stayed responsive, and concurrent pictures were rejected.
    Desktop/mobile Chrome checks passed for presets, validation, busy handling, controls, saved images and
    downloads. Windows accepted a real image-preview toast with no failure event; owner visual check pending.
  - Fixed a Windows native import-order crash found during combined testing: load the existing ONNX runtime
    before WinRT toast bindings, while keeping OCR models lazy. Also initialized each OCR test database
    independently so the full suite works regardless of which feature tests run first. After the final restart,
    a live notification followed by real OCR passed in the same running app process.
- **Phase 22: /look photo understanding** (version 0.22.0).
  - Describe it, Receipt / totals and a custom question through the photo controls or /look with an attachment.
    The shared registry adds /look to /help, /help look and the / menu.
  - app/tools/vision.py ports the bot's Gemma 3 + matching mmproj CPU llama-mtmd-cli invocation. Independent
    vision settings, empty/off on a fresh download; host-only Settings controls for paths, threads and timeout.
    The owner's existing model files are reused by local configuration without changing Studio or the bot.
  - app/photo_jobs.py accepts one background analysis at a time; the request returns immediately so chat remains
    available. The photo, progress and answer stay in the local chat but are excluded from text-model history.
    Completed answers arrive through the existing polling system and trigger the shared reply popup.
  - Progress replacement is tied to its own message, with a new migrated replaces column. Reload, deleted chats,
    process errors, timeouts, shutdown cancellation and recovery after a restart are handled. Temporary inference
    files are removed; CPU operation is enforced and the child process has no interactive input.
  - Arrival polling now advances only through the delivered batch, avoiding skipped messages.
  - Verification: all 18 automated checks passed, covering settings, CPU arguments, process timeout/cancellation,
    concurrent chat, busy rejection, completion notification calls, persistence, deletion and restart/shutdown.
    A real CPU description identified the test shapes/colors in 151 seconds; a full live app check then returned
    "A red square and a blue circle" while normal text chat also replied. Syntax, dependencies and whitespace
    checks passed. Windows notifications are enabled; the test-popup request succeeded. Ordinary popups were
    suppressed while BEYOND's page was being viewed, as intended. Owner confirmed the photo/UI test passed with a game title-screen description. Visual popup verification remains pending.
  - The vision child runs at below-normal Windows priority so text chat has scheduling priority.
- **Phase 21: photos and /scan** (version 0.21.0).
  - Photo picker and drag-and-drop, local preview, Read text, and /scan with an attached photo.
  - Ported PromptetheusBot's RapidOCR reader and receipt row/column grouping to app/tools/scan.py. Bundled
    models run on the CPU; no LLM or external OCR call. One reader at a time, with a busy response.
  - Bounded raw-image upload (10 MB), pixel and format checks (PNG/JPEG/WebP, still photos), EXIF rotation,
    transparent backgrounds flattened onto white, and metadata stripped before saving.
  - Photo and OCR output saved in the existing SQLite chat storage with separate photo/scan kinds, excluded
    from LLM history. Reload keeps both; deleting the chat removes them. Copy text includes a fallback for
    home-network devices where the Clipboard API is unavailable.
  - Added rapidocr, onnxruntime and opencv-python-headless; refreshed the exact dependency lock.
  - Verification: eight automated tests, including actual receipt OCR, persistence, LLM-history exclusion,
    invalid/oversized files, pixel bounds, busy responses, missing chats, and blank-result handling. Python
    and browser-script syntax checks, dependency checks and git diff whitespace checks. The owner confirmed
    it works after restarting BEYOND. No live chats or bot files were used by the automated tests.
- **Phase 20b: morning briefing** (version 0.20.1), ported from PromptetheusBot (one user; the voice version comes
  with the speech phase).
  - New `app/briefing.py`: your city (which also sets the time zone, via the /time and /weather place lookup),
    weekday and weekend times (or off), sections (weather with umbrella/jacket tips, today's reminders, three
    headlines from a chosen category, a quote or a joke), and an optional name for the greeting. A failing section
    is left out instead of failing the briefing. If BEYOND was off at briefing time it still comes within two hours.
  - **/morning** (alias /briefing): a menu with buttons (on/off, weekday and weekend time pickers, section toggles,
    news category, quote or joke, 📨 Send it now) and typed settings (`city`, a time, `weekends 9am`, `news tech`,
    `name Sam`, `on`, `off`, `now`).
  - The server checks every 30 seconds and posts a due briefing in the chat where /morning was last used (or a
    "☀️ Morning briefing" chat), with a "☀️ Good morning" popup (under the reminder popup setting). The page shows
    it like a reminder (`GET /api/reminders/fired` now also returns briefings).
  - Added `top_headlines()` to the news tool (left out of the Phase 13 port).
  - Tested: the menu and every button, a bad and a good city, `/morning now`, Send it now, and a briefing
    scheduled two minutes ahead that arrived on time (5:12:08 PM) with no browser open; the settings were reset
    afterwards.
- **Phase 20: tray icon and popups** (version 0.20.0).
  - `beyond.py` now runs BEYOND from a **system-tray icon** (an orange B drawn with Pillow): Open BEYOND (also a
    double-click), Pause popups, Quit BEYOND; the web server runs in a background thread and keeps running when the
    browser is closed. Started with `pythonw.exe` it has no console window and writes to `data\beyond.log`;
    `--console` runs it the old way. New dependencies: `pystray`, `pillow`, `Windows-Toasts`.
  - New `app/notify.py`, the one shared **notify** feature: `notify.show(kind, title, text, chat_id, buttons=…)`.
    A popup is shown only if its kind is on, it isn't quiet hours (also across midnight), popups aren't paused, and
    you aren't looking at BEYOND's page: the page reports every 10 seconds while it's visible and focused
    (`POST /api/presence`). Clicking a popup opens BEYOND at that chat; popup buttons call back into BEYOND.
    BEYOND registers its name and icon for popups under the Windows user (needed for buttons).
  - Popups for: **a finished AI reply**, **a reminder** (✅ Done, 😴 10 min, 😴 1 hour on the popup, with the same
    rules as the page's buttons), and **problems** (an AI error during a reply, and the AI server stopping, checked
    every minute, once per outage).
  - Settings: a "Popups and the tray" section with a switch per kind, quiet hours, **Start BEYOND with Windows**
    (new `app/autostart.py`: your user's Run entry, `pythonw.exe beyond.py`, changed only when you switch it) and
    **Send a test popup** (`POST /api/notify/test`, this PC only).
  - Fixed: two comments in `app/config.py` had been garbled by an encoding mistake in Phase 11.
  - Tested: the popup rules (each setting, quiet hours, looking at the page, Pause), a bad quiet-hours time refused,
    the registration, the startup entry switched on (checked) and off again, the test popup (seen on screen by the
    owner), and a reply and a reminder popup triggered with nobody looking (no errors).
- **Phase 19: reminders, in the app** (version 0.19.0), ported from PromptetheusBot (one user, this PC's time zone).
  - New `app/reminders.py`: the bot's reading of one-time times ("30m", "in two hours", "tomorrow at 6pm",
    "friday", "March 3") and repeating schedules (daily, weekdays, weekends, days of the week, every N hours or
    days, monthly, yearly), stored in BEYOND's database. Also refuses "yesterday at 5pm" (the bot moved it to
    today).
  - **/remind** (with ↩️ Undo) and **/reminders** (🗑 per reminder, or `/reminders cancel <number>`).
  - The server checks every 5 seconds (a background task started with the app) and posts a due reminder in the
    chat where it was set (or a "⏰ Reminders" chat if that one was deleted), with ✅ Done, 😴 10 min and 😴 1 hour.
    A repeating reminder moves on to its next time; one missed while BEYOND was off goes off once.
  - The page asks every 5 seconds (`GET /api/reminders/fired`): in the open chat the reminder appears as a message;
    otherwise a ⏰ banner names the chat and offers Open. The tab title shows ⏰ until you look.
  - Commands can now run code once their reply is saved (`Reply.on_saved`), and button handlers can read the
    pressed message (`commands.PRESSED`).
  - Tested: usage, a missing time, Undo, repeating and one-time reminders, a time in the past, /reminders with 🗑 and
    cancel by number; a 15-second reminder through the API; in the browser a 2-minute reminder that appeared in the
    open chat exactly on time (set 4:33:40 PM, shown 4:35:41 PM), a 1-minute one from another chat as a banner,
    Snooze (back in /reminders for 10 minutes later) and Done.
- **Phase 18: expenses** (version 0.18.0), ported from PromptetheusBot (one user).
  - New `app/expenses.py`: amounts stored as whole cents, this PC's local dates, ten built-in categories matched
    from words ("lunch", "gas", "rent", "costco"…), and words you teach it. Dates like "yesterday", "oct 3",
    "last friday", "3 days ago" or "last month" (new `dateparser` dependency); future dates are refused.
  - **/spent** (alias /expenses): logging with ↩️ Undo and 🏷 Change category; for an unknown word, category buttons
    or ➕ New category from the word (remembered next time). Reports for this month (daily average, change vs the
    same days last month), any month, a year (monthly average, pace, by month) and all time, each with spending by
    category and the biggest expense. `/spent recent` with 🗑 per expense; `/spent categories`.
  - 📄 **Download CSV** under every report: a new kind of button that is a link (only to BEYOND's own `/api/`
    addresses), served by `GET /api/expenses.csv?period=…` as UTF-8 with a BOM so Excel opens it.
  - Fixed while porting: "last month" was read as "month" (logged today), and "tomorrow" was accepted as today.
  - Tested: twelve expenses (categories, a taught word, a new category, Undo, past and future dates, a missing
    amount), month, last month, year and all-time reports, 🗑 in recent, categories, the CSV (download in the
    browser, columns, BOM, total) and a bad period refused.
- **Phase 17: checklists** (version 0.17.0), ported from PromptetheusBot (one user).
  - New `app/checklists.py`: up to 20 lists of 100 items in BEYOND's database; names matched loosely ("groceries",
    "my grocery list"), an icon per kind of list, duplicates skipped (adding a checked item again unchecks it).
  - **/list** (alias /lists): all lists with a button to open each; `/list <name> add a, b, c`; `/list add …` for
    the to-do list; `remove <number>`, `clear` (checked items) and `delete` (asks first). Each item is a button
    (⬜ / ✅) that checks or unchecks it in place; 🧹 Clear checked and 🗑 Delete list under it.
  - Tested: building a grocery list, a duplicate, ticking and unticking, the overview, remove, clear checked, a
    missing list, delete with Keep and with Yes (by command and by button), and ticking in the browser.
- **Phase 16: notes** (version 0.16.0), ported from PromptetheusBot's notepad (one user).
  - New `app/notes.py`: notes in BEYOND's database (up to 500 of 1,000 characters), numbered #1, #2… (numbers are
    never reused), with full-text search (word forms and prefixes), a typo-tolerant fallback, and date words
    (today, yesterday, this/last week, this/last month). Passwords, codes, card and account numbers are refused,
    like /remember.
  - **/note** (save, `find`, `delete`, `clear`, `add` for notes that start with a command word, `help`) and
    **/notes** (the 10 most recent, or `/notes <words>` to search). Buttons: ↩️ Undo after saving, 🗑 per note
    under /notes, and a confirmation before clearing all.
  - Tested: save, undo, two refused secrets, exact, misspelled ("plumbr") and date searches, /notes search, 🗑,
    delete by number (and a missing number), clear with Keep and with Yes, and the empty notepad.
- **Phase 15: small extras** (version 0.15.0), ported from PromptetheusBot's plugins.
  - **/joke** (dad, pun, nerd, absurd or any topic: icanhazdadjoke, JokeAPI in safe mode, Official Joke API, with
    the AI as a backup), **/quote** (ZenQuotes), **/cat** (catfact.ninja), **/so** (Stack Overflow), **/rewrite**
    (six tones, written by your AI; the text is wrapped so instructions inside it are rewritten, not obeyed) and
    **/qr** (links, text and Wi-Fi with the new `segno` dependency, offline).
  - Pictures in the chat: a command reply can carry an image (a PNG data URL, saved with the message in a new
    `image` column, so deleting the chat deletes it too); the page shows only BEYOND's own PNG images.
  - /qr wifi: the password is replaced by dots in the saved chat, on the page and in the chat's name (command chats
    are now created after the command runs, from its safe text); the code itself still holds it.
  - `engine.complete_blocking()` for commands that use the AI from a worker thread; one-off replies drop
    `<think>` reasoning.
  - Tested: every command live (jokes from three sources and from the AI, quote, cat fact, Stack Overflow, two
    rewrites including one hiding an instruction, usage replies); the link, text and Wi-Fi QR codes decoded
    correctly with OpenCV; the masked password in the chat, its title and the page; the picture after a reload.
- **Phase 14: automatic lookups** (version 0.14.0), ported from PromptetheusBot's `auto_actions`.
  - New `app/lookups.py`: quick Python checks (no extra AI call) pick at most one lookup per message: weather (weather
    words and a place, also in lower case; not for climate questions or "my CPU is hot"), news ("latest news
    about…"), or web search (a question about current things, with "this year" turned into the real year). A place
    Open-Meteo can't find is searched on the web instead.
  - The answer stream sends a `status` event ("🔎 Checking the weather for Paris…"), runs the lookup in a thread,
    puts the results in the notes for that reply (with today's date, "trust the results", and "say only what they
    actually state") and sends a `lookup` event. The result is saved with the answer (new `lookup` column), so the
    page shows **🔎 Looked up: …** (tap it for the sources) after a reload too. A failed lookup shows a ⚠️ line and
    tells the AI it has no current information. Try again looks it up afresh.
  - Honesty: the "Looked up" line is written by BEYOND only. A line the AI writes itself is removed (`replace`
    event), and when a question needs current information but lookups are off, the notes say no lookup was done.
  - Recall no longer brings back older exchanges whose answer you rated 👎.
  - Setting `auto_lookup` (on by default) with a switch on the Settings page; personality updated.
  - Tested with Qwen3-4B on the processor: "what's the weather in Paris?", "Is it raining in Seattle/London right
    now?", "latest news about the Artemis mission" and "Who won the World Series this year?" all looked up and
    answered from the results ("the winners haven't been determined yet", after tightening the notes); "How do
    rainbows form?" didn't trigger a lookup; with lookups off, the AI said it couldn't check instead of inventing
    the weather (it did invent it before the honesty fixes); the Looked up line and sources in the browser and after
    a reload.
- **Phase 13: web lookups** (version 0.13.0), ported from PromptetheusBot's plugins (from `requests` to `httpx`).
  - **/web** (alias /search; DuckDuckGo via the new `ddgs` dependency), **/weather** (Open-Meteo; shares the place
    lookup with /time), **/news** (BBC, NPR, Ars Technica feeds by category, Google News for any topic; feeds are
    read at most 2 MB), **/wiki** (Wikipedia), **/define** (Wiktionary with Datamuse as backup), **/movie** (alias
    /film; Wikidata and Wikipedia) and **/tv** (TVmaze), in a new "Look things up" group in /help.
  - `app/tools/web.py`: one User-Agent, redirects followed (httpx doesn't by default), and an `Unavailable` error.
    Each command turns connection problems into a plain reply ("I couldn't reach Wikipedia. Is this computer
    connected to the internet?").
  - The page turns web addresses in any message into links (built as elements, http/https only, opened in a new
    tab with `noopener noreferrer`); text is still never run as HTML.
  - Personality: lists the lookup commands and suggests them for current information.
  - Tested live: all seven commands returned current results (San Jose weather, today's headlines, Apollo 11,
    serendipity, Back to the Future, Dune 1984, Breaking Bad); empty input, unknown place and a too-long phrase;
    every command with the internet cut off; links and /help in the browser.
- **Phase 12: ratings and learning** (version 0.12.0), ported from PromptetheusBot's `answer_feedback` (one user).
  - **👍 👎 🔄 Try again** under every finished AI answer (stored on the message: new `rating`, `reason` and
    `retry_of` columns). 👎 offers six reasons or Skip; the buttons then show "👍 Thanks!" or "👎 Noted: …". The
    answer's text never changes, and the server only accepts buttons that are on that answer.
  - New `app/learning.py`: each reason adds a point to a preference (shorter, longer, accuracy, helpful, tone,
    understand); at 2 points its hint goes into the notes for every reply, saying it overrides the usual length and
    style. "Too long" also sets a firm 180-token budget; "too short" and "too long" cancel each other. 👍 fades all
    of them by half a point. Rating the same answer twice counts once.
  - Similar questions: the FTS index finds an earlier question like this one with a 👍 answer (shown as a guide)
    and one with a 👎 answer (shown as a mistake to avoid, with the reason).
  - **🔄 Try again** (`POST /api/messages/{id}/retry`) streams a different answer (temperature +0.3, with the old
    answer quoted in the notes). The old answer becomes kind `retried`: still shown, marked "🔄 Tried again below",
    but no longer sent to the AI. Only the newest answer offers 🔄; it is removed from older ones. If no new
    answer is written, the old one is put back as it was.
  - **/learned** lists what is applied and what is only being noticed, with 🧽 Reset what you learned.
  - The answer stream is now shared by new questions and Try again; it also sends the saved answer's id and
    buttons (`message` event) before `done`.
  - Personality: knows about ratings; "2–4 sentences" now gives way to a learned preference for longer answers.
  - Tested with Qwen3-4B on the processor: rating reasons and Skip; a repeated press refused (409); "too long"
    twice applied "shorter answers" and 👍 faded it; "too short" twice made the same question 87 words instead of
    51 (control with nothing learned); Try again on the newest answer (and refused on an older one); the replaced
    answer kept after reload; the similar-question notes; all in the browser too.
- **Phase 11: automatic memory** (version 0.11.0).
  - **Fact pickup**, ported from PromptetheusBot: after an answer is saved, a personal-sounding message (the bot's
    `PERSONAL_RE` filter, which skips questions and one-off plans) goes to the AI once more with a short
    fact-finding prompt (`engine.complete`, 120 tokens, temperature 0.1). Up to 3 facts are saved as `auto` and the
    page shows "🧠 Noted for next time: …" as a note under the answer (kept in the chat, never sent to the AI). It
    is skipped while another answer is being written, so it never slows a reply down.
  - **Recall**: an FTS5 index of all chat messages (kept up to date by triggers; built once for existing chats).
    Each question's keywords find up to 2 related earlier exchanges from any chat (not ones already in the
    conversation sent to the AI) and they are attached to the newest message as background, with their dates, so
    the cached start of the prompt stays the same.
  - `/memories auto on|off` and an "Automatic pickup: on/off" line in /memories; Settings has a new **Memory**
    section with both switches (`auto_facts`, `recall`, on by default).
  - Personality: BEYOND now knows it can recall older conversations and that facts are noticed automatically.
  - Tested with Qwen3-4B on the processor: "I'm a nurse and I have a cat named Luna" saved both facts (🤖) with
    the note; after a chat about the film Arrival, a new chat's "What was that movie I told you about?" answered
    *Arrival* with the saved fact removed (recall alone); notes still show after reloading a chat; switches saved and
    rejected bad values.
- **Phase 10: saved facts.**
  - `app/memory.py`: facts in the database, ported from PromptetheusBot's `memory_store` (single user): up to 40
    facts of 200 characters; never saves passwords, PINs, codes, card or account numbers; recognises the same fact
    worded differently ("My dog is named Max" = "The user's dog is named Max"); a typed fact always fits (the oldest
    automatically picked-up fact makes room, for Phase 11). Each fact is marked typed (`manual`) or picked up
    (`auto`, Phase 11).
  - Facts are added to the system prompt after the house rules, with the date each was saved ("a newer fact
    replaces an older one that conflicts"), so the AI server keeps reusing them like the personality.
  - Commands **/remember**, **/memories** (alias /facts; 🗑 per fact and 🗑 Forget all, which asks first),
    **/forget &lt;number|all&gt;**.
  - Personality: "What You Can Do Right Now" and "Memory and Privacy" now include saved facts.
  - Tested: a fact saved in one chat answered correctly in a brand-new chat ("Your dog's name is Max", "You live in
    Portland, Oregon"); duplicate, PIN, too-short and wrong-number replies; 🗑 removed the right fact; Forget all
    with Keep and with Yes.

### Fixed
- Automatic memory now notices news about your life even without "my" or "I have": "I just got a new dog named Rex", "I adopted a cat last week", "Started a new job at Tesla today". Before, those were never checked for facts at all.
- **Phones: the header scrolled out of sight** (owner's report: you had to scroll all the way up the conversation to
  reach it). Reproduced by shrinking the view to 375×450 (a phone with its keyboard open) and scrolling the page the
  way iPhones do: the header went 300 px off the top and the message box below the screen.
  - The page itself (`body`) is now pinned to the visible part of the screen (`position: fixed`), so the browser
    can't scroll the whole page; only the conversation (and the Settings content) scrolls inside it.
  - New `app/web/app-height.js` keeps the page's height and top matched to the visible area (the browser's
    `visualViewport`) whenever it changes, and again just after you tap into or out of a text box (when keyboards
    open and close), as a backup for browsers that miss a resize.
  - Android Chrome is asked to shrink the page when its keyboard opens (`interactive-widget=resizes-content`), and
    reaching the end of the conversation no longer scrolls the page behind it (`overscroll-behavior`).
  - The header is also `sticky` as an extra safety net. Stylesheet address bumped (`style.css?v=4`).
  - Tested: with the keyboard-sized view the header stays at the top, the message box sits on the bottom edge, and
    the conversation gets the space between (289 px); a whole-page scroll does nothing; the Settings page scrolls to
    its last button with the header in place. Not tested on a real phone yet.

### Changed
- **Mobile-friendly pages (owner's request, between Phases 9 and 10).** Checked at phone (375×812), sideways phone
  (812×375), tablet (768×1024) and desktop sizes:
  - Header: the BEYOND logo and the AI status overlapped on a phone; under 520 px the status is just its coloured
    dot (text kept for screen readers and as a tooltip) and the logo's letter spacing is tighter.
  - Text boxes are 16 px on phones (under 16 px, iPhones zoom in when you tap one).
  - Touch screens (`pointer: coarse`): buttons at least 44 px tall (header buttons 40 px), reply buttons 40+ px,
    larger ✎ / 🗑, chat items and command-list rows, 24–26 px checkboxes.
  - The phone chat list gets a dimmed backdrop; tapping it closes the list.
  - Full height uses `100dvh` (what's visible next to the phone browser's bars), and the header, message box, chat
    list and Settings page leave room for the notch and home bar (`viewport-fit=cover`, `env(safe-area-inset-*)`).
  - Phones: wider bubbles (92%), less padding, command list up to 45% of the height; Settings sections and the AI
    address box adapt to narrow screens.
  - Respects "reduce motion" (no animations), and the browser's bar matches BEYOND's colours (`theme-color`).
  - Browsers now **check for an updated page or style before using a saved copy** (`Cache-Control: no-cache`;
    unchanged files get a quick "not modified"). The stylesheet's address changed once (`style.css?v=2`) so
    browsers that saved the old one, phones included, pick up the new version.
  - Tested: no horizontal scrolling at any size, no header overlap, tap-target sizes as above, the backdrop closes
    the list, tablet keeps the list open, and a sideways phone keeps 246 of 375 px for messages.
- **Phase 9: buttons in chat.**
  - Messages can carry **buttons** (rows of `{label, action}`), saved with the message (new `buttons` column,
    added automatically to existing databases). Commands reply with a `Reply(text, buttons, toast)`; an action like
    `rules:del:5` is routed by its first part to a handler in `commands.ACTIONS`, which returns the message's new
    text and buttons.
  - `POST /api/messages/{id}/press` runs a press and changes the message **in place**, with an optional short
    notice under it. It only accepts actions that are on that message's own buttons (a used, made-up or other
    message's button gets "That button is no longer available"). The stream sends a `message` event with the
    saved message's id and buttons; reopened chats include them too.
  - First uses: **🎲 Roll again** under a `/roll` result (not under errors or usage), and a **🗑** per rule under
    `/rules` (removes it and shows the updated list, with "Removed: …").
  - The page draws buttons as rounded chips under the message and disables them while a press is running.
  - Tested: Roll again replaced the result three times; 🗑 removed the right rule and renumbered; the four safety
    cases were refused; reopening showed the latest text and buttons; in the browser the same bubble changed with
    no new message.
- **Phase 8: slash commands framework.**
  - `app/commands.py` rebuilt around one list of `Command` entries (name, one-line summary, example, function,
    aliases, group). `/help` (all commands, or `/help <command>`), the page's "/" menu (`GET /api/commands`) and
    **"Did you mean…?"** for mistyped commands (`difflib`) are all generated from it. Command names ignore
    capitals.
  - First tools, copied from PromptetheusBot into `app/tools/`: **/calc** (`calculator.py`), **/convert**
    (`units.py`), **/time** (`world_time.py`), **/roll** (`dice.py`). `/time`'s online place lookup now lives in
    `app/tools/places.py` (Open-Meteo geocoder, `requests` replaced by `httpx`), ready for /weather in Phase 13.
  - Commands run in a background thread (some look things up online), and a failing command gives a short
    "ran into a problem" reply instead of breaking the chat.
  - The chat page shows a **command list when you type "/"**: filters as you type, arrow keys to move, Tab or Enter
    to pick (Enter sends once a whole command is typed), Esc to close; a matching hint in the message box.
  - Personality: "What You Can Do Right Now" mentions the commands, so the AI can point people to them.
  - New library: `tzdata` (Windows has no time-zone database of its own; needed by /time).
  - Tested: all 7 commands with examples, usage text for an empty /calc, "Did you mean /calc?" for /calk and
    "/convert?" for /conver, /CALC in capitals, normal chat still answered by the AI; the "/" menu filters, picks
    with Tab and Enter, and hides on Esc, no match, or a "/" mid-sentence.
- **Phase 7: house rules.**
  - `app/rules.py`: house rules in the database (up to 25, 5–300 characters, the same rule twice is ignored),
    ported from PromptetheusBot (its link from rules to automatic lookups waits for Phase 14).
  - Rules go at the end of the personality ("always follow; a rule wins over the style above") **and** in a short
    notes block attached to the newest message (`engine.with_reply_notes`), like PromptetheusBot's notes. The note
    is what made the difference: with the rule only in the personality, "Always answer in French" was ignored
    by the 4B model in an English conversation; with the note it answered in French. Only the newest message
    changes, so prompt reuse still works.
  - `app/commands.py`, the start of the command system: **/rule &lt;text&gt;**, **/rules**, **/rule delete
    &lt;number&gt;**; unknown /commands get "I don't know the command…" instead of going to the AI. Commands and
    their replies are saved in the chat (new `kind` column in `messages`, added automatically to existing
    databases) but never sent to the AI; on the page they show with a dashed border.
  - Settings page: a **House rules** section (list with Remove, an Add box; saved straight away, from any device
    that can chat). New endpoints `GET/POST /api/rules`, `DELETE /api/rules/{id}`.
  - Personality: "What You Can Do Right Now" now includes following house rules.
  - Tested: French and "end with OVER" rules visibly changed answers and stopped when removed; commands not in
    what the AI is sent; too short, duplicate (any capitalisation), wrong number and unknown command replies;
    Settings add / remove; an existing database got the new column with its chats intact.
- **Phase 6: personality and conversation memory.**
  - `app/personality.md`: BEYOND's personality, adapted from PromptetheusBot's system prompt (same character and
    wording, named BEYOND, Telegram replaced by "a chat page in a browser on your own computer"). A **What You Can
    Do Right Now** section lists only what exists (conversation and saved chats) so the AI says it can't do
    lookups, reminders, photos or images *yet* instead of pretending; to be updated as each phase adds features.
    Asks for plain text (the page shows no Markdown yet) and 2–4 sentence answers by default. Read on every
    message, so edits apply at once.
  - The **history window** from PromptetheusBot (`engine.history_window`): up to 12 recent messages, growing from
    6 and cut back in one step, so the start of the prompt stays identical and the AI server reuses what it already
    read. Earlier messages over 1,500 characters are shortened (`engine.trim`); the question never is.
  - Answers are capped at 700 tokens (PromptetheusBot: 350, which cut off longer requests), temperature 0.7, and
    `cache_prompt` is requested explicitly. New settings in `app/config.py`: `HISTORY_LIMIT`,
    `HISTORY_MESSAGE_CHARS`, `ANSWER_MAX_TOKENS`, `TEMPERATURE`, `PERSONALITY_FILE`.
  - The "No AI set up yet" message now points to the Settings page.
  - Tested over 7 messages: Promptetheus-style answers in plain text (no Markdown in any answer); honest "can't"
    for the weather and a reminder; remembered the person's name and interest 4 messages later; after the first
    message the AI re-read only 60–229 tokens per reply. The first message of a new chat read the whole personality
    (~1,000 tokens, 42 s) because on the owner's PC the Telegram bot shares the same AI engine and replaces its
    cached prompt; with BEYOND's own engine (Phase 33) it should stay cached.
- **Phase 5: saved conversations.**
  - `app/chats.py`: chats and their messages in a SQLite database, `data/beyond.sqlite3` (git-ignored). A new chat
    is named after its first message (up to 60 characters).
  - Saving happens on the server: the page now sends only the new message and which chat it belongs to
    (`chat_id`, empty for a new chat); BEYOND saves the question, reads the recent messages from the database for
    the AI, and saves the answer when it's finished. A stopped answer is saved and marked "Stopped"; if nothing was
    answered (stopped early or the AI failed), the question is taken out again, and a brand-new chat with nothing in
    it is removed. The stream's first event now says which chat it is (`{"type": "chat", "id", "new", "title"}`).
  - New endpoints: `GET /api/chats` (list), `GET /api/chats/{id}` (open), `PATCH /api/chats/{id}` (rename),
    `DELETE /api/chats/{id}`.
  - The chat page has a **side panel**: ＋ New chat, the chat list (newest first, with time or day), ✎ rename and
    🗑 delete (with a confirmation). The open chat is kept in the address (`#chat=3`), so refreshing reopens it. On
    narrow screens the panel slides in from a ☰ button and closes when a chat is picked.
  - Tested: two chats saved and listed while answering; a full BEYOND restart kept both and reopened the right
    one; continuing the older chat used its saved messages; rename, delete, empty-name refusal, sending to a deleted
    chat, a stopped answer saved as stopped, and a failed first message leaving no empty chat; phone-width panel.
- **Phase 4: settings page** (`/settings`, linked from the chat page).
  - **AI server** address with **Test connection**, and an optional model name.
  - **Port**, refusing ports other local AI apps rely on (`RESERVED_PORTS` in `app/config.py`: Local AI Studio's
    1420 / 8080 / 10086, LM Studio 1234, Ollama 11434, Gradio 7860, ComfyUI 8188), ports below 1024, and ports
    already in use (naming the program).
  - **Allow other devices on my network** (off by default): BEYOND then listens on all networks and the page and
    console list the addresses to open on a phone; plus a Windows Firewall tip. **Settings can only be changed from
    this PC** (`127.0.0.1`); other devices see them read-only and can still chat.
  - Port and network changes need a restart: **Restart BEYOND now** makes `beyond.py` start the server again in the
    same window with the new settings (falling back to the old port if the new one was taken meanwhile); the page
    follows to the new address.
  - **Reset to defaults** deletes `data/settings.json`.
- `app/settings.py` now checks every setting (`validate`), saves **only what differs from the defaults** (`save`),
  and resets (`reset`); a bad value in the file is ignored with a warning instead of breaking BEYOND.
- `app/web/style.css`: colours (light and dark) and shared styles for every page, served at `/static/`.
- Tested: Test connection; network switch on → restart → reachable at the Wi-Fi address, settings read-only and
  saving refused from there; ports 10086, 5939 (in use) and 80 refused; 7771 → restart → back to 7770; Reset →
  no settings file, every default back, "No AI set up yet". Not tested: an actual phone (Windows Firewall may ask).
- **Phase 3: live typing and chat controls.**
  - Answers appear word by word as the AI writes them (new `/api/chat/stream`: one JSON event per line, `token` /
    `done` / `error`; `engine.chat_stream` reads the AI server's streamed reply).
  - **Stop** (the Send button turns into Stop while the AI writes; Esc works too). What was written so far stays,
    marked "Stopped", and still counts as part of the conversation. Stopping closes the connection to the AI server,
    so llama.cpp stops writing and is free straight away (checked: `requests_processing 0`, slot idle).
  - **New chat** button in the header: clears the conversation (stopping any answer in progress).
  - A "…" bubble until the first word arrives, then a blinking cursor while it writes. The page only scrolls
    along if you're already at the bottom, so you can scroll up and read during a long answer.
  - Error messages work the same as before, also in the middle of a streamed answer.
  - Message box: no scrollbar until it's full; the New chat button's name is "New chat" for screen readers too.
  - Tested in the browser: a long story streamed in and was stopped halfway; a follow-up still knew the story;
    New chat started with no memory of it; a wrong AI address gave "can't reach the AI server".
- **MIT License** (`LICENSE`, copyright 2026 Jeremy Stevens), with a License section in the README. The project is
  public on GitHub: https://github.com/jeremystevens/beyond (commits use the GitHub noreply email).
- **Phase 2: first chat.** The page is now a chat: message box (Enter sends, Shift+Enter for a new line), chat
  bubbles, a "…" bubble while the AI works, and plain-word error messages. The whole conversation is sent with
  each question (last 40 messages), so BEYOND remembers what was said earlier in the chat. The AI's words are
  shown as plain text, never run as HTML.
- `app/engine.py`, the **engine connector**: the only place BEYOND talks to an AI server, using the standard
  OpenAI-compatible chat API (llama.cpp, Local AI Studio, LM Studio, Ollama). Clear messages when no AI is set
  up, the server can't be reached, it's still loading, takes over 5 minutes, or answers with an error.
- `app/settings.py`: settings = defaults in `app/config.py` + your changes in `data/settings.json` (git-ignored),
  read on every use. A fresh install has **no AI server set** and says "No AI set up yet"; the owner's PC points
  at Local AI Studio's engine in its own `data/settings.json`, so port 10086 never appears in the code.
- Status light in the header: AI connected (with the model name), no AI set up, or can't reach the AI; checked
  every 30 seconds. New endpoints `/api/ai-status` and `/api/chat`.
- New library: `httpx` (talking to the AI server).
- Tested: fresh install (no settings file) shows "No AI set up yet"; with Studio's engine, a reply in 5 s and a
  follow-up question remembered earlier in the chat; a wrong address gives "can't reach the AI server".
- **Phase 1: project setup.** Git repository, Python 3.14 virtual environment, folder layout, README with the
  project pitch, this changelog, `.gitignore` (the `data` folder with your settings and chats is never committed).
- `beyond.py` starts a small web server (FastAPI + Uvicorn) showing a placeholder page on **port 7770**, reachable
  only from this PC by default. Before starting, it checks the port is free; if not, it names the program using it
  and how to fix it, instead of crashing.
- `app/config.py` holds the fresh-install defaults and is the only place port numbers are defined.
- `/api/health` reports that BEYOND is running, its version and phase.
- Planning documents moved into `planning/`.

[Unreleased]: https://github.com/jeremystevens/beyond/compare/v0.38.4...HEAD
[0.38.4]: https://github.com/jeremystevens/beyond/releases/tag/v0.38.4
