# Built-in tool routing and awareness audit

All 54 canonical commands in app.commands.COMMANDS are covered below. Every registered command and alias receives accurate usage help, and a compact grouped inventory is included in the stable chat prompt. The inventory is generated from the real registry rather than a second hard-coded list.

Natural routing is intentionally conservative: explicit supported requests run existing handlers, while workflows needing input, optional components or persistent changes keep their established controls. This audit does not claim that every possible spoken phrase is recognized. Routing itself adds no model request; the command inventory adds a small stable prompt block.

| Command | Request/workflow path | Awareness/help |
|---|---|---|
| `/think` | Composer checkbox or /think; existing guided mode. | Registry inventory and current summary/example (aliases included for help). |
| `/model` | Existing natural model-identity route; /model fallback. | Registry inventory and current summary/example (aliases included for help). |
| `/status` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/speed` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/selftest` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/trivia` | Existing /trivia and game controls/state. | Registry inventory and current summary/example (aliases included for help). |
| `/tictactoe` | Existing /tictactoe and game controls/state. | Registry inventory and current summary/example (aliases included for help). |
| `/hangman` | Existing /hangman and game controls/state. | Registry inventory and current summary/example (aliases included for help). |
| `/blackjack` | Existing /blackjack and game controls/state. | Registry inventory and current summary/example (aliases included for help). |
| `/quizme` | Existing /quizme and study controls/state. | Registry inventory and current summary/example (aliases included for help). |
| `/games` | Existing /games menu. | Registry inventory and current summary/example (aliases included for help). |
| `/speak` | Read aloud control or /speak; optional speech setup. | Registry inventory and current summary/example (aliases included for help). |
| `/imagine` | Existing /imagine and image controls; optional engine and explicit request. | Registry inventory and current summary/example (aliases included for help). |
| `/look` | Photo attachment/vision workflow; optional feature and explicit question. | Registry inventory and current summary/example (aliases included for help). |
| `/scan` | Photo attachment/OCR workflow; optional feature. | Registry inventory and current summary/example (aliases included for help). |
| `/help` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/writefile` | Existing file-request workflow; host/admin and Save requirements retained. | Registry inventory and current summary/example (aliases included for help). |
| `/cancelwrite` | Existing /cancelwrite; explicit pending-write cancellation. | Registry inventory and current summary/example (aliases included for help). |
| `/files` | Existing /files and file UI; host/admin restriction. | Registry inventory and current summary/example (aliases included for help). |
| `/editfile` | Existing file-request workflow; preview/Save and permissions retained. | Registry inventory and current summary/example (aliases included for help). |
| `/fileundo` | Existing /fileundo; explicit file change and permissions. | Registry inventory and current summary/example (aliases included for help). |
| `/readfile` | Existing file-reading requests and explicit /readfile path. | Registry inventory and current summary/example (aliases included for help). |
| `/filehelp` | Existing /filehelp usage guide. | Registry inventory and current summary/example (aliases included for help). |
| `/calc` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/convert` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/time` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/roll` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/searchhistory` | Existing dated/history recall route and Search history UI. | Registry inventory and current summary/example (aliases included for help). |
| `/web` | Existing explicit web/follow-up router; /web fallback. | Registry inventory and current summary/example (aliases included for help). |
| `/weather` | Existing weather/follow-up/confirmation handling; automatic lookup preference retained. | Registry inventory and current summary/example (aliases included for help). |
| `/news` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/wiki` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/define` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/movie` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/tv` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/joke` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/quote` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/cat` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/rewrite` | Writing helper UI or /rewrite; editable draft, no sending. | Registry inventory and current summary/example (aliases included for help). |
| `/qr` | Explicit /qr with content; use command usage, do not invent an image. | Registry inventory and current summary/example (aliases included for help). |
| `/so` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/note` | Existing /note and notes controls; persistent edits stay explicit. | Registry inventory and current summary/example (aliases included for help). |
| `/notes` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/list` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/remind` | Existing /remind and confirmation/schedule controls; no invented save. | Registry inventory and current summary/example (aliases included for help). |
| `/reminders` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/morning` | Existing briefing menu and schedule controls; explicit settings. | Registry inventory and current summary/example (aliases included for help). |
| `/spent` | Existing /spent expense/report workflow; logging stays explicit. | Registry inventory and current summary/example (aliases included for help). |
| `/remember` | Existing /remember and auto-fact preference; no invented save. | Registry inventory and current summary/example (aliases included for help). |
| `/memories` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/forget` | Existing /forget and memory controls; deletion stays explicit. | Registry inventory and current summary/example (aliases included for help). |
| `/learned` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |
| `/rule` | Existing /rule and rules controls; persistent changes stay explicit. | Registry inventory and current summary/example (aliases included for help). |
| `/rules` | Direct ordinary-word request routing to existing handler. | Registry inventory and current summary/example (aliases included for help). |

## Regression coverage
Tests require the inventory and this table to cover every canonical registered command; usage lookup is tested for every command and alias. Adding a command without updating this audit fails coverage. Exact cat-fact and Tokyo-time requests, polite variants, additional read-only tools and ordinary-chat/pending-file guards have focused routing tests. Side effects retain existing command permissions and confirmation flows. No tool is executed merely to build help or the inventory.

Validation: full Windows/Python 3.14 and Chromium CI passed, both reported requests passed live checks, and the user confirmed improved mobile behavior. Approved for the upcoming release as a bug fix; no release version is changed here.
