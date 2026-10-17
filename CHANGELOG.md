# Changelog

All notable changes to BEYOND are recorded here, newest first.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
