# BEYOND

**B**uilt **E**ntirely on **Y**our **O**wn **N**etwork & **D**evice

*What Local AI Studio users wanted next.*

> **Status: early development (Phase 20 of the plan in `planning/phases.md`).** You can chat with BEYOND in your
> browser: it has its own personality, follows your house rules, remembers facts about you in every chat (ones you
> tell it and ones it notices), recalls related older conversations, learns from your 👍 👎 ratings, checks the weather, news or web by itself when a question needs it, writes its
> answers as you watch (with a Stop button and 🔄 Try again), saves your conversations in a side panel, and has
> slash commands (/calc, /convert, /time, /roll, /weather, /news, /web, /wiki, /define, /movie, /joke, /qr,
> /note, /list, /spent, /remind, /remember, /help), some with buttons. It uses an AI server you already run (such as Local AI Studio); BEYOND's own built-in AI engine
> arrives in Phase 33.

## Saved facts

Tell BEYOND things to remember in **every** chat, new or old:

- **/remember &lt;fact&gt;** saves one, for example `/remember my dog is named Max` or
  `/remember I prefer metric units`.
- **/memories** lists them, with a **🗑** per fact and **🗑 Forget all** (which asks first).
- **/forget &lt;number&gt;** or **/forget all** removes them.

Up to 40 facts of up to 200 characters. The same fact twice (even worded differently) is recognised, and BEYOND never
saves passwords, PINs, codes, or card or account numbers. Facts are added to the AI's instructions with the date they
were saved, so a newer fact wins over an older one that conflicts.

**Automatic memory:**

- **Noticing facts.** When you mention something lasting about yourself in passing ("I'm a nurse and I have a cat
  named Luna"), BEYOND saves it after the answer and shows **🧠 Noted for next time** under it. Picked-up facts are
  marked 🤖 in /memories. It only runs after personal-sounding messages, never while another answer is being
  written, and skips questions, opinions and one-off plans. Turn it off with **/memories auto off** or on the
  Settings page.
- **Recalling old conversations.** Every message is indexed for search (SQLite FTS5). When you ask something like
  "what was that movie I told you about?", BEYOND finds the most related earlier exchanges in any chat and gives
  them to the AI as background for that one reply. No extra AI work; turn it off on the Settings page.

## Ratings and learning

Every answer has **👍**, **👎** and **🔄 Try again** under it.

- **👎** asks what was wrong (too long, too short, wrong or made up, not helpful, wrong tone, didn't understand
  me); you can also skip. After the same kind of complaint twice, BEYOND changes how it answers: for example
  shorter answers (with a firm word limit), more detail, extra care with facts, or a plainer tone. **👍** slowly
  undoes old complaints.
- When you ask something similar to an answer you rated, the AI is shown the one you liked as a guide and the one
  you didn't as a mistake to avoid.
- **🔄 Try again** writes a different answer to your last question. The old one stays in the chat, marked
  "Tried again below", but the AI no longer sees it. It is offered on the newest answer only.
- **/learned** shows what BEYOND picked up from your ratings, with **🧽 Reset what you learned**.

The AI itself isn't retrained; ratings change what it is told before it answers.

## Looking things up

These commands fetch current information from free public services (no accounts or API keys). Only what you type
after the command is sent; results are shown as they come, with links you can open, and are never followed as
instructions.

| Command | What it does | Source |
|---|---|---|
| `/web <question>` | Top 5 web results with a snippet each (alias `/search`) | DuckDuckGo (`ddgs` package) |
| `/weather <place>` | Now, the next 6 hours and 3 days; °F/mph in the US | Open-Meteo |
| `/news [topic]` | Headlines: top, world, us, politics, tech, science, business, health, entertainment, sports, or any topic | BBC, NPR, Ars Technica, Google News |
| `/wiki <topic>` | An article's summary | Wikipedia |
| `/define <word>` | Meanings, pronunciation and examples | Wiktionary (Datamuse as backup) |
| `/movie <title> [year]` | Year, director, runtime, cast, ratings, summary (alias `/film`) | Wikidata, Wikipedia |
| `/tv <title>` | Years, network, cast, rating, summary | TVmaze |

Without internet, each one says so plainly.

**Automatic lookups.** You don't need the commands for everyday questions. When a message clearly needs current
information, BEYOND looks it up first and the AI answers from the results:

- weather words and a place ("what's the weather in Paris?", "do I need an umbrella in London tomorrow?") → Open-Meteo
  (a place it can't find is searched on the web instead);
- "latest news about…", "any breaking news?" → the news feeds;
- other questions about current things ("who won … this year?", "price of…", "current population of…") → web search.

The page shows "🔎 Checking the weather for Paris…" while it looks, and the answer ends with **🔎 Looked up: …**;
tap it to see exactly what was found. That line is added by BEYOND, never by the AI, and BEYOND removes it if the AI
writes one itself. The decision is made by quick checks in Python (no extra AI work), and only the place, topic or
question is sent. Turn it off on the Settings page; then the AI says it can't check and suggests the command.

## Commands

Type **/** in the message box to see the commands; keep typing to narrow the list, use the arrow keys, and press
Tab or Enter to pick one. BEYOND answers commands itself, instantly, without the AI.

| Command | What it does | Example |
|---|---|---|
| `/help` | List every command, or explain one | `/help calc` |
| `/calc` | Calculator: maths, percentages, tips, splitting a bill | `/calc tip 85.50 18% split 4` |
| `/convert` | Units: temperature, distance, weight, cooking, speed and more | `/convert 72 f to c` |
| `/time` | Time in a city, several cities, or convert a time | `/time 3pm London to Tokyo` |
| `/roll` | Dice and coin flips | `/roll 2d20+3` · `/roll coin` |
| `/joke` | A dad joke, pun, nerd or absurd joke, or one about any topic | `/joke cats` |
| `/quote` · `/cat` | A random quote; a random cat fact | `/quote` |
| `/rewrite` | Say a message in another tone (professional, friendly, funny, polite, dramatic, concise), written by your AI | `/rewrite polite I can't come tomorrow` |
| `/qr` | A QR code picture for a link, text or Wi-Fi network; the Wi-Fi password is hidden in the chat | `/qr wifi Home | password` |
| `/so` | Search Stack Overflow | `/so python read a file line by line` |
| `/note` · `/notes` | A notepad: save notes, find them (typos and date words like "yesterday" are fine), delete one or all (asks first); ↩️ Undo after saving; passwords and codes are refused | `/note garage key is in the blue folder` · `/note find garage` |
| `/list` | Checklists (groceries, packing, to-dos): tap an item to check it off, 🧹 clear checked items, 🗑 delete a list (asks first); "groceries" and "my grocery list" are the same list | `/list groceries add milk, eggs` · `/list` |
| `/spent` | An expense log: `/spent 12.50 lunch` (or `… yesterday`, `… oct 3`, `… last friday`) picks a category from the words and remembers ones you choose; `/spent` shows this month, also `last month`, `october`, `year`, `2025`, `all`, with a 📄 Download CSV button (opens in Excel); `/spent recent` deletes | `/spent 45 gas yesterday` · `/spent year` |
| `/remind` · `/reminders` | Reminders in plain words, once (`30m`, `tomorrow at 6pm`, `friday`, `March 3`) or repeating (`every Monday at 8am`, `every weekday`, `every 2 hours`, `every month on the 1st`). They pop up in the chat where you set them, with ✅ Done and 😴 10 min / 1 hour; if you're in another chat, a ⏰ banner offers to open it. `/reminders` lists and cancels them | `/remind tomorrow at 6pm call Dan` |
| `/remember` · `/memories` · `/forget` | Save, list and remove facts BEYOND knows in every chat | `/remember my dog is named Max` |
| `/learned` | What BEYOND learned from your ratings, with a reset | `/learned` |
| `/rule` · `/rules` | Add, list and delete house rules | `/rule Use metric units` |

A mistyped command gets "Did you mean…?". Commands and their replies are saved in the chat but never sent to the
AI.

**Buttons:** some replies have buttons underneath, and pressing one changes that message in place: **🎲 Roll
again** under a `/roll` result, and a **🗑** for each rule under `/rules`. Buttons are saved with the message, so
they still work when you reopen the chat. BEYOND only accepts a press of a button that's actually on that message. `/calc`, `/convert` and `/roll` work fully offline; `/time` works offline for about 400 cities and looks up
other places (only the place name) with the free Open-Meteo geocoder.

## Personality

BEYOND's personality lives in `app/personality.md`: witty, curious, honest, plain-spoken, with short answers unless
you ask for more. Its "What You Can Do Right Now" section tells the AI exactly which features exist, so it says
"I can't do that yet" instead of pretending; it's updated as features are added. Edits to the file apply from the
next message, without restarting.

Each question is sent with up to the last 12 messages of the chat. To keep replies fast, the AI server reuses the
part of the prompt it already read: the personality comes first and never changes, and the chat history grows from
6 to 12 messages and is then cut back in one step, so the start of the prompt stays the same for several messages.
Very long earlier messages are shortened in what's sent.

## House rules

House rules are instructions BEYOND follows in every chat, such as "Always answer in under 3 sentences",
"Use metric units" or "Always answer in French". Up to 25 rules of 5–300 characters.

- In a chat: **/rule &lt;text&gt;** adds one, **/rules** lists them, **/rule delete &lt;number&gt;** removes one.
- On the Settings page: the **House rules** section lists them with **Remove** buttons and an **Add** box (saved
  straight away; usable from any device that can chat).

Rules are added to the end of the personality and repeated in a short note next to your newest message, because
small models follow instructions best when they're close to the question. Commands like /rules and BEYOND's
replies to them are saved in the chat but never sent to the AI.

## Chats

Every conversation is saved on your PC as you go, in `data\beyond.sqlite3`. The panel on the left lists them,
newest first: click one to open and continue it, **✎** to rename it, **🗑** to delete it, **＋ New chat** to start
another. A new chat is named after its first message. Refreshing the page or restarting BEYOND keeps your chats,
and the page reopens the chat you were in. On a phone-sized screen the panel opens with **☰**.

**On phones and tablets:** the pages adapt to the screen. On a phone the chat list slides in from **☰** (tap the
dimmed area to close it), the AI status shows as a coloured dot (its text is a tooltip and is read by screen
readers), buttons are big enough for a thumb, text boxes don't make the phone zoom in, and the layout leaves room for
the notch and home bar. The header and message box stay on screen (also with the keyboard open); only the
conversation scrolls. On a tablet or wider, the chat list stays open beside the chat. After BEYOND is updated,
browsers check for the new version of each page automatically.

If you press Stop, what the AI wrote so far is saved and marked "Stopped". If you stop it (or it fails) before it
writes anything, that question isn't saved.

## What this project is about

**Local AI Studio** loads a model and lets you chat with it.

**BEYOND** is an assistant that runs on that model and actually helps with your day:

- **Remembers you:** facts about you, your preferences, and conversations from weeks ago.
- **Learns how you like answers** from your 👍👎 ratings and house rules.
- **Knows what's happening now:** it looks up weather, news and the web on its own, and tells you when it did.
- **Keeps you organized:** reminders, checklists, notes, an expense log and a morning briefing.
- **Understands photos:** reads the text in them and answers questions about them.
- **Talks and listens,** and has games and quick tools for when you just want to have fun.
- **Looks after itself:** speed tracking, a self-test and an error history.

Everything runs on your own computer. Your chats, memories and photos stay there; only web, weather and news
lookups go online, and the assistant tells you when it used one.

## Running it (development)

Needs **Python 3.14** on Windows.

```powershell
cd D:\AI\beyond
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\pythonw.exe beyond.py
```

BEYOND starts in the **Windows tray** (the orange **B** by the clock): click it, or open
**http://127.0.0.1:7770** in your browser. Its menu has **Open BEYOND**, **Pause popups** and **Quit BEYOND**. It keeps
running when the browser is closed, so reminders still go off. What it prints goes to `data\beyond.log`. To run it in a
console window instead (no tray icon), use `.\.venv\Scripts\python.exe beyond.py --console`.

**Popups.** While you're not looking at BEYOND's page, Windows popups tell you when the AI has replied, when a
reminder goes off (with ✅ Done and 😴 Snooze right on the popup), and when something went wrong (for example the AI
server stopped answering). Clicking a popup opens that chat. Each kind can be switched off on the Settings page, with
quiet hours and a **Send a test popup** button. Settings can also add BEYOND to your Windows startup programs (**Start
BEYOND with Windows**, for your user only). BEYOND registers its name and icon for popups under your Windows user
(`HKCU\Software\Classes\AppUserModelId\BEYOND.LocalAI`), which Windows needs for the popup buttons to work.

## Settings

Click **Settings** at the top of the chat page (or open http://127.0.0.1:7770/settings).

- **AI server:** BEYOND doesn't have its own AI engine yet, so enter the address of one you already run, for
  example Local AI Studio's engine `http://127.0.0.1:10086`, and press **Test connection**. Any server with the
  standard OpenAI-compatible chat API works (llama.cpp's `llama-server`, Local AI Studio, LM Studio, Ollama).
  Takes effect at once. Until one is set, the chat page says "No AI set up yet".
- **Port:** BEYOND uses **7770** by default. You can change it; BEYOND refuses ports other AI apps rely on
  (Local AI Studio's 1420, 8080, 10086; LM Studio, Ollama, ComfyUI, Gradio) and ports already in use, naming the
  program. If 7770 is taken when BEYOND starts, it says which program has it instead of crashing.
- **Allow other devices on my network:** off by default, so only this PC can open BEYOND. Turn it on to use
  BEYOND from your phone or another computer at home; the settings page then lists the addresses to open. Leave it
  off on shared networks: there's no login yet (Phase 38). Other devices can chat but **can't change settings**.
  If a phone can't connect, Windows Firewall may be blocking Python: allow it on private networks when asked.
- The **port** and **network** settings need a restart: the page shows **Restart BEYOND now**, and BEYOND restarts
  itself in the same window (if a new port has meanwhile been taken, it stays on the old one).
- **Reset to defaults** puts every setting back as on a fresh download.

Your changes are saved in `data\settings.json`, which only holds what differs from the defaults in
`app/config.py`. The `data` folder (settings, chats, and later memories and logs) is never uploaded to the
repository, so deleting `data\settings.json` also brings back the defaults.

## Project layout

```
beyond.py            Start BEYOND: the tray icon, then the web server (checks the port, restarts after port/network
                     changes); --console runs it without the tray
app/config.py        Default settings, including every port number (the only place ports are defined)
app/settings.py      Your settings: the defaults plus your changes in data/settings.json (check, save, reset)
app/engine.py        The engine connector: the only place BEYOND talks to an AI server (and the history window)
app/personality.md   BEYOND's personality (the system prompt)
app/chats.py         Saved conversations (SQLite database in data/beyond.sqlite3)
app/rules.py         House rules (same database)
app/memory.py        Saved facts (same database)
app/learning.py      Ratings and what BEYOND learns from them
app/notes.py         The notepad (/note, /notes), in the same database
app/checklists.py    Checklists (/list), in the same database
app/expenses.py      The expense log and reports (/spent), in the same database
app/reminders.py     Reminders (/remind): reading times and schedules; the server fires them
app/notify.py        Windows popups: one shared feature (settings, quiet hours, "not while you're looking")
app/autostart.py     "Start BEYOND with Windows" (your user's startup programs)
app/lookups.py       Automatic lookups: when a question needs the weather, news or web
app/commands.py      Slash commands: one list (name, summary, example, function) drives /help, the / menu
                     and "did you mean…?"; replies can carry buttons, handled by ACTIONS
app/tools/           The tools behind the commands (calculator, units, world_time, dice, places, and the
                     online lookups: web, web_search, weather, news, wikipedia, dictionary, movies; and
                     jokes, little_lookups, rewrite, qr),
                     from PromptetheusBot
app/ports.py         Port checks (free? who's using it?) and this PC's network addresses
app/server.py        The web server (FastAPI): pages, chat, settings and status endpoints
app/web/             The pages: index.html (chat), settings.html, style.css (shared look), app-height.js
                     (keeps the page fitted to the visible screen on phones)
planning/            Brainstorm, project pitch and the phased plan
data/                Your settings, chats and logs (created at runtime, git-ignored)
```

## License

BEYOND is open source under the [MIT License](LICENSE): you're free to use, change and share it, as long as the
copyright and license notice stay with it. AI models you use with BEYOND have their own licenses from their makers.

## Planning

- `planning/project_pitch.md`: what BEYOND is about
- `planning/brainstorm_standalone_app.md`: ideas, options and decisions
- `planning/phases.md`: the step-by-step plan (43 small phases)
