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

### Phase 15: Small extras
- `/joke`, `/rewrite`, `/quote`, `/cat`, `/so`, and `/qr` (the QR code shown as a picture in the chat).
- **Done when:** each command works, and the QR code scans with a phone.

### Phase 16: Notes
- `/note`, `/notes`, `/note find`, delete, clear (with a confirmation button).
- **Done when:** notes can be saved, found, and deleted.

### Phase 17: Checklists
- `/list` with tap-to-check items, clear checked items, and delete a list.
- **Done when:** a grocery list can be built, ticked off, and cleared.

### Phase 18: Expenses
- `/spent` with categories, monthly and yearly reports, and a CSV file download.
- **Done when:** expenses are logged, a report shows totals, and the CSV opens in Excel.

### Phase 19: Reminders, in the app
- `/remind` (one-time and repeating) and `/reminders`, with the bot's natural date reading. Reminders appear in the
  chat with Done and Snooze buttons.
- **Done when:** a reminder set for 2 minutes from now pops up in the chat on time.

### Phase 20: Tray icon and popups
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

### Phase 20b: Morning briefing
- `/morning`: weather, today's reminders and headlines at a set time, delivered in the chat with a popup.
- **Done when:** the briefing arrives at its set time, with the browser closed.

---

## Stage D: Photos, pictures and voice

### Phase 21: Photos in, and `/scan`
- Drag-and-drop and a 📎 button for photos; `/scan` reads the text in them (instant).
- **Done when:** dropping a photo of a receipt and choosing "Read text" shows its text, ready to copy.

### Phase 22: `/look`
- Ask the vision AI about a photo: Describe it, Receipt / totals, or your own question (about 1–2 minutes, one at a
  time, with a progress message).
- A **popup when the answer is ready** (Phase 20's notify feature).
- **Done when:** a photo gets a correct description, chat keeps working while it's being looked at, and a popup
  says when it's done.

### Phase 23: `/imagine`
- Picture generation with **Quick / Good / Best** presets instead of raw settings, shown in the chat with a
  download button and a progress message ("about 3–5 minutes").
- A **popup when the picture is finished**, showing a small preview where Windows allows it.
- **Done when:** each preset produces a picture, chat keeps working meanwhile, and a popup says when it's ready.

### Phase 24: Better pictures
- A **prompt helper** (the chat AI turns a short idea into a detailed description), plus the usual "avoid this"
  words (blurry, extra fingers…) added automatically.
- **Done when:** a short idea like "a cat in space" gives a clearly better picture than the same words without help.

### Phase 25: Spoken replies
- `/speak` and an optional "read answers aloud" setting, with an audio player in the chat (Kokoro, Piper fallback).
- **Done when:** an answer can be played aloud in the browser.

### Phase 26: Voice input
- A microphone button: speak, and your words are turned into text and sent.
- **Done when:** a spoken question gets a normal answer.

---

## Stage E: Games (each rebuilt for the web)

The game **rules** come from the bot unchanged; only the **screens** are new (see the brainstorm file).

### Phase 27: Games menu and dice
- A games menu, `/roll` with a nicer dice display, and shared score / stats storage.
- **Done when:** the menu opens and dice rolls show.

### Phase 28: Tic-tac-toe
- A real clickable 3×3 grid, three difficulty levels, stats.
- **Done when:** a full game can be played and won, lost or drawn at each level.

### Phase 29: Trivia
- Category and difficulty pickers, answer buttons, score.
- **Done when:** a round of questions can be played with scores kept.

### Phase 30: Study quiz (`/quizme`)
- Topic quizzes that adapt to you, with Next / Stop and stats.
- **Done when:** a quiz on any topic runs and the stats update.

### Phase 31: Blackjack
- Playing cards on screen, Hit / Stand, dealer play, stats.
- **Done when:** full hands can be played, including blackjack and bust.

### Phase 32: Hangman
- The gallows drawing updating in place, an on-screen A–Z keyboard, categories, difficulty and hints.
- **Done when:** a word can be guessed or lost, with the drawing advancing on each miss.

---

## Stage F: Its own engine (no Studio needed)

### Phase 33: Built-in engine
- BEYOND starts and stops **llama.cpp** itself, with the tuned settings (processor, 12 threads, f16 cache), on a
  free port it picks automatically, and checks that it's healthy. The "connect to an existing server" option from
  Phase 2 stays available. On the owner's PC, test with a small model or with the bot paused (memory).
- **Done when:** with Studio closed, BEYOND starts its own engine and chat works.

### Phase 34: Models page
- Lists the models in BEYOND's models folder with sizes; load, unload and switch, with settings per model.
- **Done when:** switching models from the page works, and the chat uses the new one.

### Phase 35: Model downloads
- Download models from Hugging Face inside the app, with **fingerprint checks**, resume after a broken download,
  a free-disk-space check, and license links for models that need the maker's terms accepted.
- **Done when:** a model downloads, is verified, and can be loaded straight away.

### Phase 36: Status and health page
- PC status, AI speed history (`/speed`), error history, and a self-test (`/selftest`), all on one page, including
  each port BEYOND uses and whether it answers.
- **Done when:** the page shows live status and ports, and the self-test runs and reports.

### Phase 37: Other AI servers
- Test and polish "connect to an existing server" with Local AI Studio, LM Studio and Ollama.
- **Done when:** chat works through each of them.

---

## Stage G: Ready to share

### Phase 38: Login
- A simple password or login for when network access is on.
- **Done when:** another device must sign in before it can chat.

### Phase 39: Setup script
- One script that installs Python and the libraries, downloads llama.cpp (verified), and offers model presets by PC
  (8 GB / 16 GB / good graphics card) and optional extras (voice, `/look`, `/imagine`).
- **Done when:** the script takes a fresh folder to a working BEYOND.

### Phase 40: First-run setup in the app
- A welcome page for new users: pick a preset, test the AI, optional graphics-card test (processor stays the safe
  default).
- **Done when:** a first start walks you through to a working chat.

### Phase 41: Guide and licenses
- A user guide, the README with the pitch, license notices (llama.cpp, stable-diffusion.cpp and others), the name
  check (GitHub, PyPI), and a courtesy note to Tech Jarves.
- **Done when:** a new person could install and use BEYOND from the guide alone.

### Phase 42: Test on a clean PC
- Install from scratch on a fresh Windows user account (or another PC) with **no Studio, no bot and no settings
  file**, and fix whatever goes wrong. Also start another program on port 7770 to check BEYOND's conflict message.
- **Done when:** a clean install works start to finish with no manual fixes, on the default ports, and a port
  conflict gives a clear message instead of a crash.

### Phase 43: First release
- Version 1.0 on GitHub: release notes and a downloadable zip.
- **Done when:** the release page is up and the download installs correctly.

---

## Later, optional

- **Shared brain with the Telegram bot:** once BEYOND's core is stable, the bot and BEYOND could share one copy of
  the brain (memory, commands, plugins) so a fix lands in both. This would change `promptetheus-bot`, so it needs its
  own planning and the owner's go-ahead.
- **BEYOND tab in Local AI Studio**, a plugin system suggested to Tech Jarves, or other ideas from the brainstorm.
