# BEYOND: implementation phases

**Created:** 2026-10-17
**Based on:** `brainstorm_standalone_app.md` and `project_pitch.md` in this folder.

## How this plan works

- **Many small phases instead of a few big ones.** Most phases should fit in **one working session**. Each one
  ends with something you can see or try, plus a simple **"Done when"** check.
- **Each phase builds on the one before.** After Phase 3 you can already chat; after Phase 14 BEYOND is a useful
  everyday assistant; everything after that adds features, then makes it shareable.
- **Built in `D:\AI\beyond` only.** The Telegram bot (`promptetheus-bot`) and Local AI Studio are **not changed**.
  BEYOND reuses the bot's Telegram-free code (memory, reminders, plugins, game rules…) by **copying it in** and
  adapting it, phase by phase. A "shared brain" for both apps can be considered later (see the end of this file).
- **Same working rules as the bot:** a git commit at the end of every phase, a `CHANGELOG.md` entry, docs updated
  as features land, discuss bigger changes before coding, plain-language explanations.
- **Every new slash command must appear in /help, /help <command>, and the browser's / menu** through the shared
  command registry. Update the README command table and relevant usage sections, CHANGELOG.md, this plan, and
  app/personality.md's capability description alongside it (owner's requirement, 2026-10-17).
- **Git identity:** commits must use Jeremy Stevens's configured jeremystevens identity, with no AI co-author
  credit or Co-authored-by trailer (owner's requirement, 2026-10-17).
- **On this PC, AI runs on the processor only** (the NVIDIA card crashes every engine).

## Running alongside PromptetheusBot on the owner's PC

The owner's PC also runs PromptetheusBot and Local AI Studio, so BEYOND must stay out of their way. A fresh install
on someone else's PC won't have this problem, but the same rules keep it robust there too.

Ports listening on the owner's PC (checked 2026-10-17):

| Port | Used by |
|---|---|
| 1420 | Local AI Studio's web page (open to the home network) |
| 10086 | Studio's AI engine (llama-server), used by the bot (this PC only) |
| 8080 | Studio's image engine (when started) |
| 5939, 9080, 5040, 5146, 5354, 5563, 7865 | TeamViewer, Nahimic and Windows / background services |

The bot itself uses **no port** (it fetches messages from Telegram).

**Rules for BEYOND:**
1. **Web page default port: 7770**, changeable in Settings. It avoids the ports above and those other AI apps
   commonly use (7860 Gradio, 8000, 8080, 8188 ComfyUI, 1234 LM Studio, 11434 Ollama, 3000). At startup BEYOND
   checks the port is free and gives a clear message if not.
2. **Its own engine (Phase 33) picks a free port automatically.** Only BEYOND uses it, so it never collides with
   Studio's 10086.
3. **Its own data folder:** chats, memories, settings and reminders are never shared with the bot's `data` folder.
4. **Its own tray icon and name**, distinct from the Promptetheus Control Center.

**A fresh download must work out of the box (owner's requirement, 2026-10-17).** The owner's PC will point BEYOND at
Studio's engine on 10086 for most of development; that must never become the default for a new user.
5. **Defaults live in the code and are always the fresh-install values** (web page 7770, built-in engine on an
   automatic port; "connect to an existing server" is an option, never the default).
6. **The owner's own settings file is never committed** (it's git-ignored, like the bot's `.env` and `data`), so a
   fresh clone has no settings file and uses the clean defaults.
7. **Port numbers are defined in exactly one place** in the code, never repeated (lesson from the bot's `E:\` paths,
   which were spread over five files).
8. **Port checks at every start:** if the web port is taken, a clear message names the program using it and how to
   change the port (no crash); if the engine port is taken, another one is picked automatically; if the AI server
   can't be reached, the page says so plainly.
9. **The self-test and status page list each port and whether it answers.**
10. **Tested as a stranger would use it** (Phase 42): a clean Windows user account with no Studio, no bot and no
    settings file, plus a deliberate conflict on port 7770 to check the message.

**During development on the owner's PC:**
- Phases 2–32 use Studio's engine on 10086 ("connect to an existing server"), so no second model is loaded. The bot
  and BEYOND take turns with the AI; one may wait a few seconds if both answer at once.
- Phase 33 (own engine) would load a second model: about 3–4 GB more memory and shared processor time. Test it with a
  small model, or pause the bot briefly.

## Milestones at a glance

| After phase | What you have |
|---|---|
| 3 | Chat with the AI in your browser, answers appearing as they're written |
| 7 | It has its personality, remembers your chats, and has a settings page |
| 14 | An everyday assistant: memory, house rules, ratings, slash commands, web lookups |
| 20b | Your personal tools: notes, lists, expenses, reminders, morning briefing; a tray icon and popups for replies, reminders and errors |
| 26 | Photos, `/look`, `/imagine` and voice |
| 32 | All the games, rebuilt for the web |
| 37 | Runs its own AI engine: no Studio needed, models page, status page |
| 43 | Ready to share: login, installer, first-run setup, guide, first release |

---

## Stage A: Foundation (chat in the browser)

### Phase 1: Project setup ✅ (done 2026-10-17)
- Git repository, Python 3.14 virtual environment, folder layout, `.gitignore`, `README.md` (with the pitch),
  `CHANGELOG.md`.
- A tiny web server showing a "BEYOND" placeholder page on port **7770** (see "Running alongside PromptetheusBot"),
  with a free-port check and a clear message if it's taken. Its own `data` folder.
- **Done when:** opening the page in the browser shows the placeholder while the bot and Studio keep running
  normally, and the first commit is made.

### Phase 2: First chat ✅ (done 2026-10-17; the AI server address is a setting, empty on a fresh install)
- A simple chat page: message box, Send button, chat bubbles.
- One small **engine connector** file that sends messages to an AI server in the standard OpenAI format. At first
  it points at Studio's engine on port 10086, which is already running.
- **Done when:** you type a question in the browser and get the AI's answer back.

### Phase 3: Live typing and chat controls ✅ (done 2026-10-17)
- Answers appear word by word as they're written (streaming).
- **Stop** button, **New chat** button, a "thinking…" indicator, and a clear message when the AI isn't reachable.
- **Done when:** a long answer streams in, can be stopped halfway, and a new chat starts clean.

### Phase 4: Settings ✅ (done 2026-10-17; settings can only be changed from this PC; phone not tested yet)
- A settings file plus a settings page: AI server address, BEYOND's port, and the **"Allow other devices on my
  network"** switch (on for you, off by default when shared).
- Defaults stay in the code (fresh-install values); the settings file only stores your changes and is git-ignored
  (rules 5–7 in "Running alongside PromptetheusBot").
- **Done when:** changing a setting on the page takes effect; your phone on the home network can open BEYOND with
  the switch on (and can't with it off); and deleting the settings file brings back the fresh-install defaults.

### Phase 5: Saved conversations ✅ (done 2026-10-17)
- Chats are saved in a small database, so refreshing the page or restarting BEYOND keeps them.
- A side panel listing past chats: open, rename, delete.
- **Done when:** you restart BEYOND and your earlier chats are still there.

---

## Stage B: The brain (what makes it more than "chat with a model")

### Phase 6: Personality and conversation memory ✅ (done 2026-10-17; keep "What You Can Do Right Now" in `app/personality.md` up to date in every later phase)
- Bring over Promptetheus's system prompt (personality) and the "recent messages" window, using the fast
  prompt layout from the bot (stable parts first, so the AI can reuse what it already read).
- **Done when:** BEYOND answers in Promptetheus's style and remembers what was said earlier in the chat.

### Phase 7: House rules ✅ (done 2026-10-17; /rule and /rules started the command system early)
- A list of house rules added to every chat (add, list, delete), from the settings page and with `/rule` / `/rules`.
- **Done when:** a rule like "always answer in under 3 sentences" visibly changes the answers.

### Phase 8: Slash commands framework ✅ (done 2026-10-17)
- Typing `/` shows a command list; `/help` lists every command; mistyped commands get a "did you mean…?"
- First easy commands to prove it works: `/calc`, `/convert`, `/time`, `/roll`.
- **Done when:** those four commands work and `/help` lists them.

### Phase 9: Buttons in chat ✅ (done 2026-10-17; used by /roll "Roll again" and /rules 🗑)
- Messages can carry buttons (like Telegram's buttons under a message), and pressing one updates that message in
  place. This is needed by ratings, lists, reminders and the games.
- **Done when:** a test command shows buttons, and pressing them changes the message.

### Between 9 and 10: Mobile-friendly pages ✅ (done 2026-10-17, owner's request)
- Responsive layout for phones, sideways phones and tablets; touch-sized buttons; no zoom-on-tap; notch and home bar
  room; browsers always check for an updated page. **Every later page should keep working at phone size.**

### Phase 10: Saved facts ✅ (done 2026-10-17)
- `/remember`, `/memories`, `/forget`, and saved facts added to every chat.
- **Done when:** after `/remember my dog is named Max`, a new chat answers "What's my dog's name?" correctly.

### Phase 11: Automatic memory ✅ (done 2026-10-17)
- Automatic fact pickup ("🧠 Noted for next time"), with the filter for non-facts, and searching old conversations
  so "what was that movie I told you about?" works weeks later.
- **Done when:** a fact mentioned in passing is picked up, and a detail from an old chat is recalled.

### Phase 12: Ratings and learning ✅ (done 2026-10-17)
- 👍 👎 🔄 under every answer, 🔄 Try again, and `/learned` (what it learned from your ratings, with reset).
- **Done when:** rating answers changes later ones, and `/learned` shows what it picked up.

### Phase 13: Web lookups ✅ (done 2026-10-17)
- `/web`, `/weather`, `/news`, `/wiki`, `/define`, `/movie` and `/tv`.
- **Done when:** each command returns current information.

### Phase 14: Automatic lookups ✅ (done 2026-10-17)
- The AI decides by itself when to check the web, weather or news, and ends with "🔎 Looked up: …".
- **Done when:** asking "what's the weather in Paris?" in plain words triggers a lookup and says so.

---

## Stage C: Personal tools

### Phase 15: Small extras ✅ (done 2026-10-17)
- `/joke`, `/rewrite`, `/quote`, `/cat`, `/so`, and `/qr` (the QR code shown as a picture in the chat).
- **Done when:** each command works, and the QR code scans with a phone.

### Phase 16: Notes ✅ (done 2026-10-17)
- `/note`, `/notes`, `/note find`, delete, clear (with a confirmation button).
- **Done when:** notes can be saved, found, and deleted.

### Phase 17: Checklists ✅ (done 2026-10-17)
- `/list` with tap-to-check items, clear checked items, and delete a list.
- **Done when:** a grocery list can be built, ticked off, and cleared.

### Phase 18: Expenses ✅ (done 2026-10-17)
- `/spent` with categories, monthly and yearly reports, and a CSV file download.
- **Done when:** expenses are logged, a report shows totals, and the CSV opens in Excel.

### Phase 19: Reminders, in the app ✅ (done 2026-10-17)
- `/remind` (one-time and repeating) and `/reminders`, with the bot's natural date reading. Reminders appear in the
  chat with Done and Snooze buttons.
- **Done when:** a reminder set for 2 minutes from now pops up in the chat on time.

### Phase 20: Tray icon and popups ✅ (done 2026-10-17)
- BEYOND runs from a **system-tray icon** (Open BEYOND, Pause popups, Quit) and keeps running when the browser is
  closed. It can start with Windows.
- **Windows popups** (notifications) so you know something happened while you're doing something else:
  - **the AI has finished replying** (only when you're not looking at BEYOND's page, so no popups while you watch);
  - **a reminder is due** (with Done / Snooze);
  - **something went wrong** (for example the AI engine stopped).
- Clicking a popup opens BEYOND at that message. Each kind of popup can be switched on or off in Settings, with
  quiet hours.
- Built as one shared "notify" feature, so later phases just plug into it.
- **Done when:** with BEYOND's page in the background, a finished reply, a due reminder and a test error each show
  a popup, and clicking one opens the right chat.

### Phase 20b: Morning briefing ✅ (done 2026-10-17)
- `/morning`: weather, today's reminders and headlines at a set time, delivered in the chat with a popup.
- **Done when:** the briefing arrives at its set time, with the browser closed.

---

## Stage D: Photos, pictures and voice

### Phase 21: Photos in, and `/scan` ✅ (done 2026-10-17; automated OCR/API checks passed; owner confirmed it works after restarting)
- Drag-and-drop and a 📎 button for photos; `/scan` reads the text in them (instant).
- **Done when:** dropping a photo of a receipt and choosing "Read text" shows its text, ready to copy.

### Phase 22: `/look` (implemented 2026-10-17; 18 automated checks and live CPU/concurrent-chat checks passed; owner confirmed photo/UI test passed; visual popup check pending)
- Ask the vision AI about a photo: Describe it, Receipt / totals, or your own question (about 1–2 minutes, one at a
  time, with a progress message).
- A **popup when the answer is ready** (Phase 20's notify feature).
- **Done when:** a photo gets a correct description, chat keeps working while it's being looked at, and a popup
  says when it's done.

### Phase 23: `/imagine` (implemented 2026-10-17; 30 automated checks and all three live presets passed; owner UI/popup check pending)
- Picture generation with **Quick / Good / Best** presets instead of raw settings, shown in the chat with a
  download button and a progress message ("about 3–5 minutes").
- A **popup when the picture is finished**, showing a small preview where Windows allows it.
- **Preset estimates on this CPU:** Quick ~1–2 minutes, Good ~3–5 minutes, Best ~9–12 minutes (256/8, 384/12,
  512/15). These are estimates, not completion timers.
- Ported the bot's standalone DreamShaper worker; own background CPU process, progress persisted in chat,
  one image at a time, PNG download, preview popup, bounded timeout and shutdown/restart recovery.
- /help, /help imagine and the browser menu use the shared command registry; README, personality and changelog updated.
- **Done when:** each preset produces a picture, chat keeps working meanwhile, and a popup says when it's ready.

### Phase 24: Better pictures (implemented 2026-10-17; 41 checks passed; matched live comparison completed; owner quality/UI review pending)
- A **prompt helper** (the chat AI turns a short idea into a detailed description), plus the usual "avoid this"
  words (blurry, extra fingers…) added automatically.
- Improve prompt is optional and reviewable, with edit/undo, bounded requests and protection against late results
  after navigation. Original prompts still work when the chat AI is unavailable.
- Automatic negative prompts respect lettering and explicit monochrome/coloring-book styles. Prompt and avoid
  words stay with the saved image request. /help imagine, browser menu, README and personality are updated.
- **Done when:** a short idea like "a cat in space" gives a clearly better picture than the same words without help.

### Phase 25: Spoken replies (implemented 2026-10-18; 56 checks passed; browser playback verified; owner listening check pending)
- `/speak` and an optional "read answers aloud" setting, with an audio player in the chat (Kokoro, Piper fallback).
- Ported Kokoro/Piper to a separate CPU process; queued generation keeps chat available, persists audio with
  answers, and supports retry, restart recovery and browser seeking. Automatic reading is optional and off by default.
- Added host settings, Read aloud controls, shared /help and command menu entries, README and personality guidance.
- **Done when:** an answer can be played aloud in the browser.

### Phase 26: Voice input ✅ (done 2026-10-17; a spoken question got a normal answer; owner confirmed 🎤 works from another PC over the secure https:// address)
- A microphone button: speak, and your words are turned into text and sent.
- **Done when:** a spoken question gets a normal answer.

---

## Stage E: Games (each rebuilt for the web)

The game **rules** come from the bot unchanged; only the **screens** are new (see the brainstorm file).

### Phase 27: Games menu and dice (implemented 2026-10-18; all 80 tests passed; browser verified; owner play check passed)
- A games menu, `/roll` with a nicer dice display, and shared score / stats storage.
- Games header button and /games open quick dice/coin choices; later games show their planned phases.
- Saved visuals use the actual server roll, including kept/dropped dice, repeats and totals. /games stats
  shows shared local totals, independent of chat deletion; score/outcome storage is ready for later games.
- Shared /help, command menu, README, personality and changelog updated.
- **Done when:** the menu opens and dice rolls show.

### Phase 28: Tic-tac-toe (implemented 2026-10-18; all 96 tests passed; browser verified; owner play check passed)
- A real clickable 3×3 grid, three difficulty levels, stats.
- **Done when:** a full game can be played and won, lost or drawn at each level.

### Phase 29: Trivia (implemented 2026-10-18; all 111 tests passed; browser verified; owner test passed 2026-10-18)
- Category and difficulty pickers, answer buttons, score.
- /trivia and Games start rounds of up to five questions from the bot's sources, with source/license credits.
- Bot scoring is unchanged: Easy/Medium/Hard earn 1/2/3 points; wrong answers reset the streak.
- Saved private rounds resume after reload/restart. Duplicate/stale answers cannot score twice; shared points,
  accuracy and streaks save atomically with progress. /trivia score and /games stats show saved records.
- Updated shared /help, command discovery, README, personality and changelog.
- **Done when:** a round of questions can be played with scores kept.

### Phase 30: Study quiz (`/quizme`) (implemented 2026-10-18; all tests passed; browser verified; owner play check passed 2026-10-18)
- Topic quizzes that adapt to you, with Next / Stop and stats.
- **Done when:** a quiz on any topic runs and the stats update.

### Phase 31: Blackjack ✅ (done 2026-10-18; tests passed and owner played it)
- Playing cards on screen, Hit / Stand, dealer play, stats.
- **Done when:** full hands can be played, including blackjack and bust.

### Phase 32: Hangman ✅ (done 2026-10-18)
- The gallows drawing updating in place, an on-screen A–Z keyboard, categories, difficulty and hints.
- **Done when:** a word can be guessed or lost, with the drawing advancing on each miss.

---

## Stage F: Its own engine (no Studio needed)

### Phase 33: Built-in engine (implemented 2026-10-18)
- BEYOND starts and stops **llama.cpp** itself, with the tuned settings (processor, 12 threads, f16 cache), on a
  free port it picks automatically, and checks that it's healthy. The "connect to an existing server" option from
  Phase 2 stays available. On the owner's PC, test with a small model or with the bot paused (memory).
- **Done when:** with Studio closed, BEYOND starts its own engine and chat works.

### Phase 34: Models page (implemented 2026-10-18; Models tested; mobile navigation review pending)
- Lists the models in BEYOND's models folder with sizes; load, unload and switch, with settings per model.
- Responsive cards on phones and computers; link from chat and Settings. Shows the current Phase 33 model
  without copying it, scans local GGUF subfolders, and allows existing files to be added from the host PC.
- Per-model threads, context, cache and thinking persist in local settings. Known models can be selected and
  tuned from a phone. General settings, executable selection and adding host paths stay local-PC-only.
- Unload stays off across restarts. A matching healthy process is required before chat can use the selected
  model; switching/unloading cannot interrupt an active AI request. Slow loads can be cancelled or changed.
- Essential engine checks: three model-switch safeguards and ten existing engine checks passed with temporary
  stand-ins; syntax/HTML/whitespace checks and HTTP/HTTPS availability passed.
- Owner confirmed the Models feature works. Mobile feedback moved Games and Models into the hamburger drawer,
  keeping Settings in the header; the revised mobile layout is ready for the owner to review.
- **Done when:** switching models from the page works, and the chat uses the new one.

### Phase 34a: Personas (implemented 2026-10-18; playtest pending)
- A small addition before downloads: Settings → Persona offers Normal, Professional, Sarcastic, Evil and Funny.
- Normal keeps the existing personality. Other presets add chat role instructions without replacing house rules,
  memories, accuracy or tool limitations; one-off AI jobs keep their own prompts.
- Save persona changes only the speaking style. It applies to the next reply, persists locally, and needs no
  app restart or model reload. Reset to defaults restores Normal.
- Persona can be selected from phones as well as the host PC, like house rules. General settings stay local.
- **Done when:** the saved style affects the next chat reply, switching back restores Normal, and the control
  works on phone and desktop. Jeremy will playtest; inspect logs if anything fails.

- **Performance follow-up (0.34.5):** personas are now off by default, with an explicit Use a persona switch.
  Off suppresses optional role instructions while retaining the chosen preset, base personality, rules and
  memories. First-turn engine logs show uncached prompt processing; Normal already had an empty role block,
  so no speedup is claimed. Owner comparison pending.

### Phase 34b: Search history (implemented 2026-10-18; playtest pending)
- Independent, dated SQLite records for useful lookup commands and automatic web/weather/news lookups. Exclude
  jokes, quotes, cat facts and games. Keep bounded result snapshots, sources, origin/status and UTC/local times.
- /searchhistory (/searches) and explicit past-search questions retrieve actual matching records without an LLM.
  Date/tool/word filters and Search again run a fresh lookup with a new dated history entry.
- Settings → Search history works on phones and computers; browse filters, source links and selected-only bulk
  deletion. Deleting a chat does not delete history; deleting history does not delete chats.
- **Done when:** a lookup remains recallable after its chat is deleted, a date query finds it, Search again runs
  fresh results, and bulk deletion removes just the selected records. Jeremy will playtest.

### Phase 34c: Natural lookup follow-ups (completed and playtested 2026-10-18)
- Save the latest successful lookup subject and bounded real result per chat. Comparisons reuse weather, news,
  wiki, define, movie and TV tools; web/Stack Overflow comparisons clarify replacement versus added context.
- Weather place/day follow-ups run fresh lookups. Movie/TV field questions use sourced result data, resolve
  the actual title and do not invent missing facts. Other short references can provide grounded AI notes.
- Persist context across reloads/restarts, isolate chats, clear new topics/failures, and preserve brief thanks.
  Fresh lookups are recorded once in search history; cached field answers are not new searches.
- **Done when:** /weather London → “What about Paris?” runs Paris weather, /movie Alien → “Who directed it?”
  answers for the resolved film, and different chats do not share subjects.
- **Verified:** three focused routing/context checks passed. Jeremy completed the playtest and approved the feature
  on 2026-10-18.

- **Follow-up fix (0.34.4):** resolve a weather clarification plus a location in the next user turn, including
  a short confirmation of an unresolved request. Run the lookup instead of letting the AI promise it.
  Keep context within this chat and respect automatic lookups. Shared place parsing accepts city/state names
  without a comma (including Denver Colorado/Denver CO), and a failed lookup accepts a corrected location.
  Save pending weather requests per chat and message; suggest close US state spellings, then execute the real
  lookup after a natural confirmation or the explicit button. Pending requests survive restarts and end after
  a new topic. Seven focused routing/state checks passed; owner recheck pending.

### Phase 34d: Optimized and custom chat prompts (implemented 2026-10-18; owner playtest pending)
- Replace the long feature-manual system prompt with a 257-word default and a 59-word Python app contract. Add
  detailed tool notes only when the current question needs them; memories, house rules and optional personas remain.
- Settings → Chat prompt can enable and save a custom prompt, show its size, restore the optimized default, and work
  on phone or computer. Custom text is limited to 16,000 characters and applies to the next reply without a restart.
- Improve & optimize uses the loaded chat model as a one-off editor, shows progress, refuses while the model is busy,
  and returns an unsaved, reviewable draft with Undo. Saving remains explicit, and the app contract still prevents
  invented tools, permissions or unfinished actions.
- **Performance follow-up (0.34.7):** after loading a built-in model, pre-read the stable system prompt with a
  one-token hidden request before reporting Ready. This shifts the cold prompt cost into startup; it never creates
  a chat message and a failure falls back to normal first-reply processing.
- Focused checks use stand-in AI replies, plus Python/browser syntax, HTML ID and whitespace checks. Jeremy
  confirmed the real CPU result: the warmed request reused 740 tokens, processed 99 new prompt tokens in 3.7 seconds,
  generated 41 tokens in 5.1 seconds, and completed in 8.78 seconds (shown as 9s).
- **Done when:** the optimized default answers normally, a saved custom prompt changes the next reply, and an
  AI-improved draft can be reviewed, undone or saved from phone and desktop.

- **Web follow-up correction (0.34.8):** keep built-in /web awareness in the small always-present app contract.
  Explicit web requests run the existing Python tool, including “look it up” after an ordinary factual question
  without a previous lookup. Resolve the topic from recent user turns in this chat, ask if unclear, and preserve
  progress, sources/history and explicit-request behavior when automatic lookups are off. Owner playtest pending.

- **Polite-request correction (0.34.9):** “yes please look it up for me” and other polite wrappers route to the
  web tool. Extract the subject from indirect factual questions and skip prior search requests on retry.
  The exact reported exchange is covered with stand-in results; owner playtest pending.

### Phase 35: Model downloads (implemented 2026-10-20)
- Download models from Hugging Face inside the app, with **fingerprint checks**, resume after a broken download,
  a free-disk-space check, and license links for models that need the maker's terms accepted.
- **Done when:** a model downloads, is verified, and can be loaded straight away.

### Phase 36: Status and health page (completed and playtested 2026-10-20)
- PC status, AI speed history (`/speed`), error history, and a self-test (`/selftest`), all on one page, including
  each port BEYOND uses and whether it answers.
- Integrated after the pushed Phase 35 model-download work; existing download routes and controls are preserved.
- Mobile-responsive cards, Settings link, light/dark theme, 10-second optional auto-refresh that pauses when hidden.
  Speed history reads existing saved stats; self-test only checks endpoints/settings/SQLite/files and never runs
  inference, downloads, model loading or service restarts. Error summaries persist locally with a 200-record cap.
- Shared /help, command discovery, README and API documentation are updated. Isolated checks use temporary data
  and stand-in HTTP services. Nine checks and isolated ASGI route/self-test verification passed, along with static
  syntax/HTML/documentation checks. Jeremy confirmed the page and self-test work after restart.
- **Diagnosis follow-up (0.36.1):** Diagnose on a recent error gathers fresh health facts and asks the loaded AI
  for likely causes, evidence and next steps. Basic advice works without a ready or idle AI; a two-minute limit and
  a single-diagnosis guard keep requests bounded. No repair or model-loading action is performed.
  Add test error and Clear test errors manage only a labelled simulated timeout. No chat/raw logs/private settings
  are sent to the AI. Jeremy tested the simulated entry and confirmed diagnosis works.
- **Low-memory follow-up (0.36.2):** RAM below 1 GiB available warns on Status, self-test and diagnosis.
  A fixed warning stays alongside AI explanations, including for simulated errors. Jeremy verified this at 0.6 GiB
  available. Seven focused diagnosis checks passed. No automatic action is taken.
- **Done when:** the page shows live status and ports, and the self-test runs and reports.

### Phase 37: Other AI servers (deferred: come back to it later)
- Test and polish "connect to an existing server" with Local AI Studio, LM Studio and Ollama.
- **Done when:** chat works through each of them.
- **Status (2026-10-20):** the connection itself already exists (Settings → AI engine → "An AI server I already
  run") and is proven with Local AI Studio. Ollama is installed on the owner's PC; LM Studio is not, so it can't be
  tested yet. Set aside to investigate and test later. Polish to look at then:
  - a model dropdown filled from the server's own model list (Ollama needs a model name);
  - a "Find servers" button that checks the usual ports (Studio 10086, LM Studio 1234, Ollama 11434);
  - keeping a thinking model's thinking out of the answer through Ollama / LM Studio (only fixed for the built-in
    engine so far);
  - checking that the stats line gets the model and token counts from each server.

---

## Stage G: Ready to share

### Phase 38: Login (implemented 2026-10-20)
- A simple password or login for when network access is on.
- **Done when:** another device must sign in before it can chat.

### Phase 39: Setup script (in progress)
- **39B implemented:** Setup.cmd / setup.ps1 / setup.py discover or offer Python 3.14, verify the installer publisher,
  and create/validate an isolated environment. Read-only checks and bootstrap tests pass. Clean-PC installation
  still needs Phase 42 validation.
- **39C implemented:** text-only dependency lock, verified CPU engine/model setup, hardware and available-memory
  checks with Retry, isolated app startup and real chat tests, preserved settings and optional shortcut/launch.
  Disposable-copy integration passed with Qwen3 0.6B.
- **39D preview implemented:** Add-Features.cmd selects independent Whisper, Kokoro, Piper, OCR, vision and image
  components with pinned downloads and isolated offline tests. Real Whisper/Kokoro/Piper/OCR integration and
  rerun skipping passed. Owner approved deferring full pinned vision/image inference to the fresh-machine Phase 42 test; keep existing apps and connected work sessions running. 39D remains a preview until those checks pass.
- **39E implemented:** recoverable interrupted transfers, bounded/logged library workers, cancellation cleanup,
  strict optional menu choices, and setup recovery documentation. Local recovery acceptance is verified;
  no-Python/fresh-PC and pinned vision/image inference acceptance remain deferred to Phase 42.
- Detailed design: phase39-setup-plan.md. Source audit: phase39-audit.md.
- One script that installs Python and the libraries, downloads llama.cpp (verified), and offers model presets by PC
  (8 GB / 16 GB / good graphics card) and optional extras (voice, `/look`, `/imagine`).
- **Done when:** the script takes a fresh folder to a working BEYOND.

### Phase 40: First-run setup in the app (implemented 2026-10-21; fresh-machine acceptance in Phase 42)
- A responsive welcome guide for fresh installations reuses Setup's model and connection, shows installed versus
  available RAM, and offers Keep current, Lighter and Balanced CPU presets. Existing configured users are not
  forced through it; Settings can reopen it.
- A fixed short greeting verifies the current AI before Open chat; failures, loading, occupied AI, timeouts and
  changed settings permit retry. Set up later is an explicit skip, not a passing result. Progress is local and
  separate from chats. Settings, tests and completion are restricted to the PC owner/administrator.
- CPU remains the supported mode. The optional graphics-card test is deferred until a compatible GPU backend
  exists; no GPU inference or large-model tests run on the busy development PC.
- Validation details: phase40-welcome.md. Browser flow uses a disposable server and simulated AI response;
  full fresh-machine validation remains Phase 42.
- **Done when:** a first start walks you through to a working chat.

### Phase 41: Guide and licenses (documentation implemented 2026-10-21; clean-PC walkthrough in Phase 42)
- Added docs/USER_GUIDE.md from download through setup, welcome, everyday use, optional features, networking,
  backups, updates and recovery. README links the guide and third-party notice index.
- Collected 91 version-matched Python dependency records, 118 shipped notice texts, and supplemental upstream
  engine/model/package materials with source/hash provenance. BEYOND's MIT license remains separate from them.
- Name checks found the unrelated PyPI beyond package; use this GitHub repository, not pip install beyond.
  Tech Jarves is acknowledged and a courtesy note is saved as an unsent draft.
- Details: phase41-guide-licenses.md. Final release-artifact/native-library and model-term review remains Phase 43.
- **Done when:** a new person could install and use BEYOND from the guide alone.

### Phase 42: Test on a clean PC (tested paths accepted; explicit exceptions retained)
- Separate-PC ZIP setup with existing Python 3.14.5, model download, welcome, normal chat, persistence and
  rerun passed by Jeremy report. Fixed shortcut port-conflict dialog and recovery were retested successfully.
- Whisper tiny, Kokoro, OCR, vision and image generation were installed and manually tested successfully
  by Jeremy. The last three raw logs/revisions were not collected; fresh-PC Piper is unconfirmed.
- No-Python bootstrap is untested and deferred by owner decision; no clean environment is available.
  Manual official Python 3.14 x64 installation followed by Setup.cmd is the documented fallback.
- Details: phase42-clean-install.md. No claim that every acceptance case passed; measured disk use remains pending.

### Phase 43: First release (published 2026-10-22)
- Draft notes: ../docs/RELEASE_NOTES.md. Packaging/checklist: phase43-release.md.
- Prepare source ZIP, consistent version/tag, checksums and exact-artifact notice review; disclose Phase 42 exceptions.
- Published v1.0.0: https://github.com/jeremystevens/beyond/releases/tag/v1.0.0. Full CI passed at the tagged commit; source ZIP, notice hashes, checksum and latest-release status verified.
- **Done when:** the release page is up and the download installs correctly.

---

### Phase 44: Code block usability (v1.0.1 candidate)

- High-priority improvement selected from post-v1-feature-brainstorm.md: fenced blocks, offline highlighting, per-block Copy code and Save code, and unchanged whole-reply Copy.
- Default and custom chat prompts receive code-fence guidance; no extra model call or Python runtime dependency.
- Parser, filename, browser, safety, streaming/reopen and prompt checks are covered. See phase44-code-blocks.md for current validation and release status.

### Phase 45: Easy updates

- Item 13 of post-v1-feature-brainstorm.md. BEYOND checks the `VERSION` file on GitHub against the running version
  and, when a newer release is out, offers **Update now** in Settings → Updates (this PC or an administrator only).
- Update now downloads and verifies `Update-Beyond.ps1`, which waits for BEYOND to close, swaps the program files,
  updates the libraries, keeps data, models, files and the Python environment, restarts BEYOND, and rolls back on
  failure. 1.0.0 users run `Update-Beyond.cmd` once by hand.
- **Done when:** a real 1.0.0 installation updates in one go with everything kept, and a failed update leaves a
  working BEYOND. See phase45-updates.md for the full plan and the open decisions.

### Phase 46: Adjust this answer

- Item 5 of post-v1-feature-brainstorm.md. A ✨ button on the newest AI answer offers Simpler, More detail, Show an
  example and Walk me through it. The choice is saved as the user's message and answered below like any reply.
- **Done when:** each choice gives a sensible reply with a small CPU model, and only the newest answer can be
  adjusted. See phase46-adjust-answer.md.

### Phase 47: Conversation branches

- Item 1 of post-v1-feature-brainstorm.md. ⑂ under any AI answer makes a new chat with the conversation up to
  that answer; the original stays as it was. Branches link back to their original and are marked in the list.
- **Done when:** a branch continues on its own, deleting either chat keeps the other, and recall doesn't repeat
  copied exchanges. See phase47-branches.md.

### Phase 48: Conversation attachments

- Item 10 of post-v1-feature-brainstorm.md. 📎 attaches a PDF, Word or text file to a chat; each question gets the
  whole of a short document or the best-matching passages of a long one, with page numbers. Only the text is kept.
- **Done when:** questions about specific pages and summaries work with a small CPU model, and removing or deleting
  clears the text. See phase48-attachments.md.

### Phase 49: Expanded rewrite and Writing helper

- Item 11 of post-v1-feature-brainstorm.md, explicitly selected by Jeremy. Keep the quick command and add guided polishing, email replies and professional/technical document drafts.
- All 13 requested tones plus the three retained legacy styles; audience/detail controls, 13 document types, opt-in attached sources, revision and draft-only Copy/Save.
- No new runtime dependency or data migration. Both version fields and the release signal remain unchanged until a release is prepared under docs/RELEASING.md.
- Validation and limits: [phase49-writing-helper.md](phase49-writing-helper.md). Live MSI testing requires the remote PC to reconnect.

### Phase 50: Pick up where we left off

- Item 2 of post-v1-feature-brainstorm.md: on-demand recap above a saved chat, with decisions, unfinished questions and suggested next steps grounded in source messages.
- Reuse a private cache until the conversation changes, allow explicit refresh, and remove it with the chat. Long history uses bounded excerpts with an explicit coverage warning. No extra AI request on normal replies or chat opening.
- No runtime package, database schema or version/release-signal changes. See [phase50-recaps.md](phase50-recaps.md) for validation and limitations.

### Phase 51: Screenshot troubleshooting

- Dedicated **Troubleshoot this** photo action, clipboard-image attachment, optional user context and reader choice. Reuse optional OCR/CPU vision and existing background photo lifecycle.
- Ground advice in bounded evidence, distinguish observations from possible causes, ask focused questions and keep evidence/advice in recent chat context. No automated repairs, dependency or schema changes, or release version changes.
- Details and checks: [phase51-screenshot-troubleshooting.md](phase51-screenshot-troubleshooting.md).

### Phase 52: Local error report preview and export

- Final item in the selected four-feature batch. Extend existing error history with user notes, optional local environment facts, best-effort redaction, editable preview and exact Copy/Save as text.
- No raw log/chat reads, AI calls, server probes or GitHub submission. Future submission/duplicate matching remains separate. No runtime dependency, database migration or release version changes.
- Scope and validation: [phase52-local-error-reports.md](phase52-local-error-reports.md).

### Phase 53: Optional GitHub reporting and duplicate checks · 1.2.0

- Counts repeated retained local error summaries; explicitly searches public GitHub issues by a report reference/category. Open/closed matches are suggestions, not proof of the same cause.
- Reviewed browser handoff uses GitHub sign-in and its final Submit button. No stored token or automatic issue creation; long drafts support Copy/paste. Simulated entries stay local; offline/rate-limit results are explicit.
- Release 1.2.0 bundles Phases 49–53. See [phase53-github-reporting.md](phase53-github-reporting.md) and [release validation](release-1.2.0-validation.md).

## Completed after 1.2.0 (unreleased)

- [Think it through and compact composer tools](think-it-through.md): + popup, visible device toggle, /think one-question command, bounded guided passes and retry metadata.

- [Conversation working notes](conversation-working-notes.md): reviewed per-chat context, explicit drafting/updating, pause/clear and history invalidation.

- [Answer checking](answer-checking.md): optional calculator, attached-document and public-search evidence checks in the existing reply menu.

- [Recent error history](clear-error-history.md) can be cleared after confirmation by the host PC or a signed-in administrator; raw logs are preserved.

- [Host status and model awareness](chat-host-status.md): /status, /model, direct spoken/typed model identity questions and runtime context. Release version and phase remain unchanged until release preparation.
- [Small-model capability ideas](small-model-capability-ideas.md) are saved for discussion only; none has been selected for implementation.

## Later, optional

- **Shared brain with the Telegram bot:** once BEYOND's core is stable, the bot and BEYOND could share one copy of
  the brain (memory, commands, plugins) so a fix lands in both. This would change `promptetheus-bot`, so it needs its
  own planning and the owner's go-ahead.
- **BEYOND tab in Local AI Studio**, a plugin system suggested to Tech Jarves, or other ideas from the brainstorm.

- [Python code syntax checks](python-code-checks.md): completed labelled Python blocks, bounded local checks, persisted results, no execution or automatic repair (unreleased; implemented).
