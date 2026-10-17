# BEYOND

**B**uilt **E**ntirely on **Y**our **O**wn **N**etwork & **D**evice

*What Local AI Studio users wanted next.*

> **Status: early development (Phase 1 of the plan in `planning/phases.md`).** Right now BEYOND only shows a
> placeholder page. Chat arrives in Phase 2.

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

- **Port:** BEYOND uses port **7770** by default. If another program already uses it, BEYOND says which one and
  stops instead of crashing. (Changing the port from a settings page comes in Phase 4.)
- **Network:** by default BEYOND is reachable **only from this PC**.
- **Your data** (settings, chats, memories, logs) goes in the `data` folder, which is never uploaded to the
  repository.

## Project layout

```
beyond.py            Start BEYOND (checks the port, then runs the web server)
app/config.py        Default settings, including every port number (the only place ports are defined)
app/ports.py         Port checks: is a port free, and which program is using it
app/server.py        The web server (FastAPI)
app/web/             The web page(s)
planning/            Brainstorm, project pitch and the phased plan
data/                Your settings, chats and logs (created at runtime, git-ignored)
```

## Planning

- `planning/project_pitch.md`: what BEYOND is about
- `planning/brainstorm_standalone_app.md`: ideas, options and decisions
- `planning/phases.md`: the step-by-step plan (43 small phases)
