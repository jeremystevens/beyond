# Changelog

All notable changes to BEYOND are recorded here, newest first.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
