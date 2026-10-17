# BEYOND

**B**uilt **E**ntirely on **Y**our **O**wn **N**etwork & **D**evice

*What Local AI Studio users wanted next.*

> **Status: early development (Phase 2 of the plan in `planning/phases.md`).** You can chat with an AI in your
> browser, using an AI server you already run (such as Local AI Studio). Chats aren't saved yet (Phase 5), and
> BEYOND's own built-in AI engine arrives in Phase 33.

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

**Connecting an AI (for now):** BEYOND doesn't have its own AI engine yet, so point it at one you already run.
Create `data\settings.json` with that server's address, for example Local AI Studio's engine:

```json
{ "ai_server_url": "http://127.0.0.1:10086" }
```

Any server with the standard OpenAI-compatible chat API works (llama.cpp's `llama-server`, Local AI Studio,
LM Studio, Ollama). Changes take effect at once, without restarting. Without this file, the page says
"No AI set up yet". The status light at the top shows whether the AI is connected.

- **Port:** BEYOND uses port **7770** by default. If another program already uses it, BEYOND says which one and
  stops instead of crashing. (Changing the port from a settings page comes in Phase 4.)
- **Network:** by default BEYOND is reachable **only from this PC**.
- **Your data** (settings, chats, memories, logs) goes in the `data` folder, which is never uploaded to the
  repository.

## Project layout

```
beyond.py            Start BEYOND (checks the port, then runs the web server)
app/config.py        Default settings, including every port number (the only place ports are defined)
app/settings.py      Your settings: the defaults plus your changes in data/settings.json
app/engine.py        The engine connector: the only place BEYOND talks to an AI server
app/ports.py         Port checks: is a port free, and which program is using it
app/server.py        The web server (FastAPI): the page, /api/health, /api/ai-status, /api/chat
app/web/             The chat page
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
