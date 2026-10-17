# BEYOND

**B**uilt **E**ntirely on **Y**our **O**wn **N**etwork & **D**evice

*What Local AI Studio users wanted next.*

> **Status: early development (Phase 11 of the plan in `planning/phases.md`).** You can chat with BEYOND in your
> browser: it has its own personality, follows your house rules, remembers facts about you in every chat (ones you
> tell it and ones it notices), recalls related older conversations, writes its answers as you watch (with a Stop button), saves your
> conversations in a side panel, and has slash commands (/calc, /convert, /time, /roll, /remember, /help), some
> with buttons. It uses an AI server you already run (such as Local AI Studio); BEYOND's own built-in AI engine
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
| `/remember` · `/memories` · `/forget` | Save, list and remove facts BEYOND knows in every chat | `/remember my dog is named Max` |
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
.\.venv\Scripts\python.exe beyond.py
```

Then open **http://127.0.0.1:7770** in your browser.

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
beyond.py            Start BEYOND (checks the port, runs the web server, restarts it after port/network changes)
app/config.py        Default settings, including every port number (the only place ports are defined)
app/settings.py      Your settings: the defaults plus your changes in data/settings.json (check, save, reset)
app/engine.py        The engine connector: the only place BEYOND talks to an AI server (and the history window)
app/personality.md   BEYOND's personality (the system prompt)
app/chats.py         Saved conversations (SQLite database in data/beyond.sqlite3)
app/rules.py         House rules (same database)
app/memory.py        Saved facts (same database)
app/commands.py      Slash commands: one list (name, summary, example, function) drives /help, the / menu
                     and "did you mean…?"; replies can carry buttons, handled by ACTIONS
app/tools/           The tools behind the commands (calculator, units, world_time, dice, places), from
                     PromptetheusBot
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
