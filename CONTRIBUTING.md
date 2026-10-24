# Contributing to BEYOND

Thanks for wanting to help! BEYOND is a private AI assistant that runs entirely on your own PC. Bug reports, ideas,
documentation fixes and code are all welcome. This guide covers how to get set up and what a good contribution
looks like.

By taking part you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Found a security problem? Please
**don't** open a public issue: see [SECURITY.md](SECURITY.md).

---

## Ways to help

- **Ask or share in [Discussions](https://github.com/jeremystevens/beyond/discussions):** questions go in Q&A,
  ideas in Ideas, and your setup in Show and tell. Issues are kept for things that are broken.
- **Report a bug** with the [bug report form](https://github.com/jeremystevens/beyond/issues/new/choose). Steps to
  reproduce it and the matching lines from `data\beyond.log` help the most.
- **Suggest a feature** with the feature request form. Explain the problem it solves, not only the solution.
- **Improve the docs:** README, help text, comments. Small fixes are very welcome.
- **Write code:** look for issues labelled `good first issue` or `help wanted`, or open an issue first for anything
  bigger, so we can agree on the approach before you spend time on it.

## Getting set up

You need **Windows 10 or 11** and **Python 3.14**.

```powershell
git clone https://github.com/jeremystevens/beyond.git
cd beyond
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe beyond.py --console
```

Then open <http://127.0.0.1:7770>. `--console` keeps BEYOND in a console window (handy while developing) instead of
the tray. To chat you need an AI: choose a `llama-server.exe` (a CPU build of llama.cpp) and a `.gguf` model in
**Settings → AI engine**, download one on the **Models** page, or point BEYOND at an AI server you already run.

Your chats, settings and logs live in `data\`, models in `models\` and written files in `files\`. All three are
git-ignored, so they never end up in a commit.

## Running the tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

The tests use temporary folders and stand-ins for the AI, the web and Hugging Face, so they don't need a model or
an internet connection and never touch your own data. Run the tests for the area you changed while you work, for
example `python -m unittest tests.test_files`, and the whole suite before opening a pull request. GitHub also runs
the whole suite on Windows for every pull request and every push to `main` (the **Tests** workflow), and shows
the result on the pull request.

The chat page's code blocks also have browser tests, which need [Node.js](https://nodejs.org/) (only for
development, not for running BEYOND):

```powershell
cd tests\web
npm ci
npx playwright install chromium
npm test
npm run test:browser
```

The **Tests** workflow runs these too, as the "Code blocks, Chromium" job.

## How the code is organised

| Where | What |
|---|---|
| `beyond.py` | Starts BEYOND: tray icon, web server (HTTP and HTTPS), restarts |
| `app/server.py` | The FastAPI app: chat streaming, settings and the API |
| `app/commands.py` | Every slash command, its help text and its buttons |
| `app/engine.py` | The only place BEYOND talks to the AI |
| `app/config.py` | Defaults, the version number and every port |
| `app/tools/` | The tools behind the commands (weather, web search, games' rules…) |
| `app/web/` | The pages: plain HTML, CSS and JavaScript, no framework or build step |
| `tests/` | One test file per feature |
| `planning/phases.md` | The roadmap, phase by phase |

The README's [Project structure](README.md#structure) section has the full tree.

### Adding a slash command

1. Write a function that takes the text after the command and returns a `Reply` (or plain text).
2. Add a `Command(...)` entry to `COMMANDS` in `app/commands.py`, with a one-line summary, an example and a group.
   It then shows up in `/help` and the "/" menu automatically.
3. Add tests, and a line to the Commands table in the README.

## Guidelines

- **Keep it local and private.** BEYOND's promise is that your data stays on your PC. Don't add telemetry, accounts
  or cloud services. Anything that goes online (like a web search) must be something the user asked for and can
  see.
- **It runs on a processor.** BEYOND targets ordinary PCs with no graphics card. Keep CPU and memory use in mind,
  and don't make a feature depend on a GPU.
- **Safety first.** Treat text from the web, files and the AI as data, never as instructions. Check paths stay
  inside BEYOND's own folders. Settings and anything touching the PC's files are for this PC or an administrator
  only.
- **Plain words everywhere.** Messages, help text and comments are written for a non-technical person: say what
  happened and what to do next, without jargon.
- **Match the code around you:** standard library first, small functions, a short comment explaining *why* when
  it isn't obvious, and no new dependency without a good reason (add it to both `requirements.txt` and
  `requirements-lock.txt`).
- **Pages:** no frameworks or build tools. Make sure a change works on a phone as well as a computer, in light and
  dark mode.

## Commits and pull requests

1. Fork the repository and create a branch from `main` (for example `fix/reminder-snooze`).
2. Keep each pull request to one change. Small pull requests are reviewed much faster.
3. Write commit messages in plain language that explain what changed and why, like you'd tell a person.
4. Add or update tests, and update the docs:
   - `CHANGELOG.md`: a line under **Unreleased** ([Keep a Changelog](https://keepachangelog.com/en/1.1.0/) style);
   - `README.md`: if commands, settings or behaviour that users see changed.
5. Run the full test suite, then open the pull request and fill in the template.

Thanks again, and welcome aboard!
