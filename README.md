# BEYOND

**B**uilt **E**ntirely on **Y**our **O**wn **N**etwork & **D**evice

*What Local AI Studio users wanted next.*

> **Status: early development (Phase 28 of the plan in `planning/phases.md`).** You can chat with BEYOND in your
> browser, by typing or by speaking (🎤): it has its own personality, follows your house rules, remembers facts about you in every chat (ones you
> tell it and ones it notices), recalls related older conversations, learns from your 👍 👎 ratings, checks the weather, news or web by itself when a question needs it, writes its
> answers as you watch (with a Stop button and 🔄 Try again), saves your conversations in a side panel, and has
> slash commands (/calc, /convert, /time, /roll, /weather, /news, /web, /wiki, /define, /movie, /joke, /qr,
> /note, /list, /spent, /remind, /morning, /scan, /look, /imagine, /speak, /games, /tictactoe, /quizme, /remember, /help), some with buttons. It uses an AI server you already run (such as Local AI Studio); BEYOND's own built-in AI engine
> arrives in Phase 33.

## Games and dice

Open **Games** in the header or type **/games**. Dice, coins, tic-tac-toe and the study quiz are available now; the
menu shows the planned phases for trivia, blackjack and hangman. Quick buttons roll a d6 or d20, flip a coin,
or show **Game stats**. Opening Games keeps any message draft or photo attachment in place.

- **/roll** rolls a d6. **/roll 2d20+3**, **/roll 4d6kh3**, **/roll 4d6dl1**, **/roll adv+5**,
  **/roll dis**, **/roll d%**, **/roll 6x 4d6kh3** and **/roll coin** keep the bot's existing rules.
- Results show dice faces or values, dropped dice, repeated-roll totals and an overall total. The plain text
  and the visual use the same server-generated roll; reopening a saved chat never rolls again.
  Large rolls show at most 60 visual dice, with every result still in the text above.
- **Roll again** makes a fresh roll and updates that result. **Games** returns to the menu.
- **/games stats** shows totals shared across chats and devices on this BEYOND installation. Each successful
  /roll or Roll again counts as one play, including any repeats requested together. Coin flips have a separate
  play count; dice track cumulative totals and the highest total. Invalid input and opening menus do not count.
- Shared stats survive restarting BEYOND and deleting a chat. The local, gitignored SQLite database stores
  these totals in `game_stats`; `app/games.py` also supports scores and win/loss/draw records for later games.
  No Telegram accounts, imported bot scores or AI calls are needed.

## Tic-tac-toe

Choose **Play tic-tac-toe** in Games, or type **/tictactoe** (**/ttt** is an alias), then choose a difficulty.
You are **X**, BEYOND is **O**, and you move first on a real clickable 3×3 board.

- **Easy** picks a random empty square. **Normal** takes a win or blocks yours, prefers the centre/corners,
  and sometimes makes a loose move. **Impossible** uses the bot's unchanged minimax rules and never loses:
  your best result against it is a draw.
- **/tictactoe easy**, **/tictactoe normal** and **/tictactoe impossible** start directly at that difficulty.
  Each move includes BEYOND's reply. Winning lines are highlighted and finished boards cannot be played again.
- **New game** starts another board at the same difficulty. **Change difficulty** returns to the picker.
  Earlier boards stay in the chat; unfinished ones remain playable after reloading or restarting BEYOND.
- **/tictactoe stats** shows wins, losses and draws for each difficulty. **/games stats** includes the combined
  tic-tac-toe record. Stats are shared across chats/devices and remain when a chat is deleted.
- Moves, board state and completed-game stats save in one SQLite transaction. Stale or duplicate clicks are
  rejected and refresh the board, so the same result counts once. Visible unfinished boards refresh when
  played from another device. Deleted boards cannot be resurrected.
- Game logic is local and does not call the chat AI. Boards are attached to their saved chat messages;
  there is no Telegram user/session dependency or 15-minute expiry.

The rules live in `app/tools/tictactoe.py`; `app/tictactoe.py` handles saved boards and per-difficulty stats,
using Phase 27's shared score store for the aggregate record.

## Study quiz (/quizme)

Choose **Start a quiz** in Games, or type **/quizme** for the topic buttons, or **/quizme <topic>** to start.

- **Math topics are instant and offline:** addition, subtraction, multiplication, division, percentages, squares,
  mixed math, or a times table (**/quizme 7 times table**). Answers are exact, and a wrong answer shows a worked
  explanation.
- **Any other topic** (*world capitals*, *spanish verbs*, *python*…) gets multiple-choice questions written by your
  AI. They take a little while on a processor-only PC and may contain mistakes; each is marked as AI-written.
- Every question has **four answer buttons** (for math, the wrong ones are typical slips: off by one or ten, a
  neighbouring times-table answer), plus **Skip** and **Stop**. After answering, **Next question ▶** continues.
- **It adapts:** each topic has levels 1–5. Three right in a row moves you up; two wrong in a row moves you down.
- **/quizme stats** shows your level, score and best streak per topic; **/games stats** counts each answer.
  Progress is saved and shared across your chats and devices. One quiz runs at a time; it ends after 15 idle
  minutes, and **/quizme stop** ends it now.

`app/study_quiz.py` holds the question makers (ported from PromptetheusBot) and the saved progress.

## Spoken replies

- **/speak** reads the last AI answer in the current chat; **/speak &lt;text&gt;** reads your own words
  (up to 1800 characters). **Read aloud** under a normal answer does the same without another command.
- Enable **Spoken replies** in Settings on the host PC. Select a Kokoro ONNX model and voice pack, and a
  Piper ONNX voice with its matching `.onnx.json` file. Kokoro is the default; a failed Kokoro run tries
  Piper automatically. You can also choose Piper directly. Existing local model files can be reused.
- **Read answers aloud automatically** is optional and off by default. It applies to new, completed normal
  AI answers. Both manual and automatic reading show progress and leave chat available while speech is made.
- Use the saved audio player's Play, Pause and seek controls. Browsers may require a Play click before allowing
  automatic playback. Only the visible, focused chat attempts automatic playback; navigating pauses its audio.
- Speech runs locally in a separate CPU process (two threads by default), one clip at a time, with a queue of
  at most four requests and a configurable timeout (180 seconds by default). No cloud speech service is used.
  Long answers read their first 1800 cleaned characters, with a notice beside the player.
- Clips are saved with the answer in BEYOND's SQLite database and remain playable after reloading or restarting.
  Changing the voice affects future clips; deleting a chat removes its clips. Errors offer Retry audio, and
  an interrupted request can be retried after restarting. Owner settings and audio stay out of git.

Implementation: `app/tools/speech_worker.py` adapts the bot's Kokoro/Piper engines with explicit CPU sessions;
`app/tools/speech.py` bounds and validates the subprocess output; `app/speech_jobs.py` queues, persists and
serves the clips, including byte ranges for browser seeking.

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
| `/scan` | Attach a photo, then extract its printed text locally; results have Copy text | Attach a photo, then `/scan` |
| `/imagine <idea>` | Make a local picture with a prompt helper, automatic defect avoidance, presets, background progress, a popup and Download PNG | `/imagine a cartoon cat in space` |
| `/look` | Attach a photo, then ask the local vision AI; Describe it, Receipt / totals, or a custom question | Attach a photo, then `/look what is on the table?` |
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
| `/morning` | A daily **morning briefing** at your times (weekdays and weekends): the weather for your city, today's reminders, three headlines, and a quote or a joke. It arrives in the chat where you set it up, with a popup, even with the browser closed. `/morning` opens a menu with buttons; `/morning city …`, `/morning 7:30`, `/morning name …`, `/morning now` | `/morning city San Carlos, CA` · `/morning on` |
| `/remember` · `/memories` · `/forget` | Save, list and remove facts BEYOND knows in every chat | `/remember my dog is named Max` |
| `/learned` | What BEYOND learned from your ratings, with a reset | `/learned` |
| `/rule` · `/rules` | Add, list and delete house rules | `/rule Use metric units` |

A mistyped command gets "Did you mean…?". Commands and their replies are saved in the chat but never sent to the
AI.

**Buttons:** some replies have buttons underneath, and pressing one changes that message in place: **🎲 Roll
again** under a `/roll` result, and a **🗑** for each rule under `/rules`. Buttons are saved with the message, so
they still work when you reopen the chat. BEYOND only accepts a press of a button that's actually on that message. `/calc`, `/convert` and `/roll` work fully offline; `/time` works offline for about 400 cities and looks up
other places (only the place name) with the free Open-Meteo geocoder.

## Photos and text scanning

Attach a **PNG, JPEG or WebP** with the 📷 button, or **drop one onto the chat**. Choose **Read text** or send
**/scan** with the photo attached. The result has a **Copy text** button (also works on devices using the home
network). Photos must be at most **10 MB / 25 megapixels**; phone rotation is handled automatically.

The bot's **RapidOCR** reader runs locally on the CPU, with its small models included in the package. The first
scan loads the reader; later scans are usually quicker. Printed text works best; handwriting and blurred photos
may read incorrectly. Only one scan runs at a time, and other requests get a clear busy message.

The prepared photo and extracted text are saved in this chat on your PC and remain after a reload. Deleting the
chat removes them. Metadata is stripped from the saved photo. Neither is sent to the chat model or online
services. Use /look below for a vision-model answer.

## Photo understanding (/look)

Attach a photo and choose **Describe it**, **Receipt / totals**, or type a question in the photo question box and
choose **Ask a question**. Sending **/look** describes the attached photo; **/look <question>** asks your question.
The same image limits as /scan apply.

BEYOND saves a progress message and starts a separate **CPU vision process** at background priority on Windows.
**You can keep chatting, change
chats or close the browser** while it works. Usually allow about 1–2 minutes; loading the model or a busy PC can
take several minutes. One photo analysis runs at a time; another request gets a clear busy reply.

The result is saved in the same chat, replacing its progress message. A **Windows popup** opens that chat when
clicked; it follows **When the AI has replied**, quiet hours, Pause popups and the existing rule to suppress
popups while you are looking at BEYOND. Failures use the error-popup preference. Restarting BEYOND interrupts a
running analysis and leaves a clear retry message. Deleting its chat discards the result without recreating it.

On the host PC, open **Settings → Photo understanding (/look)** and select a CPU **llama-mtmd-cli.exe**, a
**Gemma 3 vision model (.gguf)**, and its **matching mmproj projector (.gguf)**, then enable it and Save.
Threads and timeout are adjustable; CPU operation is enforced. File paths are stored only in your local settings,
with empty paths and the feature off on a fresh download. Built-in model downloads come in a later phase.

The photo and answer stay on this PC. Temporary inference files are deleted after the process exits. This does
not switch the model in Local AI Studio or send photos to the chat server. The vision answer can misread unclear
details; use /scan for quick printed-text extraction.

## Picture generation (/imagine)

Type **/imagine <picture idea>** in chat. Optionally choose **Improve prompt**, review or edit the result,
then choose a preset. **Undo improvement** restores the idea from before the last improvement.

| Preset | Picture size | Steps | Approximate CPU time on the development PC |
|---|---|---|---|
| Quick | 256 × 256 | 8 | About 1–2 minutes |
| Good | 384 × 384 | 12 | About 3–5 minutes |
| Best | 512 × 512 | 15 | About 9–12 minutes |

One picture runs at a time. BEYOND saves progress immediately and runs its own **CPU sd-cli.exe** at below-normal
Windows priority. Keep chatting, switch chats or close the browser while it works. Actual times depend on the PC
and other work. A second picture request gets a busy reply. The text model in Studio stays loaded.

The result replaces its own progress message in the same chat, with a **Download PNG** button that also works
when you return later or use another device on your network. Generated pictures and prompts stay in BEYOND's
database and are excluded from text-chat history and recall. Deleting the chat removes its pictures and popup
previews. Failed or interrupted jobs leave a retry message; shutdown stops and reaps the child process.

A completion popup includes a small picture preview where Windows supports it; clicking opens the chat. It uses
**When the AI has replied**, quiet hours, Pause popups and the existing rule to skip popups while you are looking
at BEYOND. Errors use the error-popup preference. If a preview cannot be attached, the text popup still works.

On the host PC, enable **Settings → Picture generation (/imagine)** and select **sd-cli.exe from its CPU folder**
and a **DreamShaper .safetensors model**, then Save. Default timeout is 20 minutes so Best has room to finish;
threads and timeout are adjustable. Fresh installs have the feature off and empty file paths. Your paths stay
in git-ignored local settings. No additional Python dependencies, Studio model switching, GPU calls, or image
server are needed. Temporary generation files are removed after each job; small popup previews live in
data/image-previews.

**Better pictures (Phase 24).** Improve prompt asks your existing chat AI for a concise, more detailed image
description. It is told to preserve the subject, count, colors, style and exclusions, including line drawings and
coloring-book art. Nothing is generated until you choose a preset. Review the rewrite first; AI suggestions can
still change a detail. Edit it or use Undo improvement if needed. Chat remains available while the helper works.
The helper has a one-minute timeout; errors leave your original idea intact, and you can generate without it
even if the chat AI is unavailable. Closing the panel or changing chats discards late helper results.

Every picture automatically avoids common defects: blur, low quality/resolution, watermarks, signatures, extra
fingers/limbs and distorted anatomy. Unwanted text is also avoided unless you request lettering or signage.
Explicit monochrome/coloring-book requests also avoid color; coloring books and requests for no shading avoid
shading, gradients and gray fill. The actual prompt and avoid words are saved with the request in its chat.
These are guidance to DreamShaper, not guarantees. No extra model or dependency is required.

For reproducible API comparisons, POST /api/imagine also accepts an optional integer seed (-1 for random, or
0–2147483647). Browser users still choose presets only; ordinary generations remain random.

## Voice input (🎤)

Tap **🎤** next to the message box, speak, and tap **⏹**: your words are turned into text **on this PC** and sent
like a typed message (anything already in the box is kept in front of them). Recording stops by itself after two
minutes. While the words are being worked out the button shows ⏳; a short question takes a couple of seconds.
If an answer is still being written, the words wait in the box for you to send.

- Speech recognition is **Whisper "base"** via faster-whisper, on the processor only (the same model and settings
  as PromptetheusBot's voice notes). The model (about 145 MB) is downloaded once from Hugging Face the first time
  you use the microphone and then works offline.
- The recording is never kept: it is written to a temporary file for the decoder and deleted straight away. Only
  the words become part of the chat.
- One recording is turned into text at a time; a second one at the same moment gets a "still working" reply.
- Browsers only allow the microphone on a secure page: **http://127.0.0.1 on this PC** works. On another computer
  or a phone, use BEYOND's **secure address**, `https://<this PC's address>:7771` (see below); on its plain
  `http://…:7770` address the 🎤 button is greyed out and offers that link.

**The secure address for other devices.** With *Allow other devices on my network* on, BEYOND also serves itself
over HTTPS on the next port (7771 by default), listed in Settings and in `data\beyond.log`. No company vouches for
BEYOND's certificate, so the first time each device's browser warns that the connection isn't private: choose
**Advanced → Continue**. It's still only your own network. If port 7771 is busy, BEYOND keeps running on 7770 only
and says so.

**Skip the warning for good:** in Settings (under the network addresses) choose **⬇ Download certificate** on the
other device and install it once; **How to install it** has the steps for Windows, Android, iPhone/iPad and Mac.
That file is BEYOND's own small *certificate authority* ("BEYOND on <your PC>", valid 10 years). BEYOND signs its
server certificate with it and renews that automatically (new network address, yearly), so a device that installed
the authority keeps trusting BEYOND without reinstalling. For safety it is limited by *name constraints* to
home-network addresses (10.x, 172.16–31.x, 192.168.x, 127.x) and this PC's name: even if its key were copied, it
could never vouch for real websites. Everything lives in `data\https` (the downloadable file holds no secrets).

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
app/briefing.py      The morning briefing (/morning): settings, schedule and the text; the server sends it
app/notify.py        Windows popups: one shared feature (settings, quiet hours, "not while you're looking")
app/autostart.py     "Start BEYOND with Windows" (your user's startup programs)
app/https.py         The secure (https://) address for other devices: BEYOND's own certificate
app/lookups.py       Automatic lookups: when a question needs the weather, news or web
app/commands.py      Slash commands: one list (name, summary, example, function) drives /help, the / menu
                     and "did you mean…?"; replies can carry buttons, handled by ACTIONS
app/tools/           The tools behind the commands (calculator, units, world_time, dice, places, and the
                     online lookups: web, web_search, weather, news, wikipedia, dictionary, movies; and
                     jokes, little_lookups, rewrite, qr),
                     from PromptetheusBot
app/tools/scan.py    Offline photo text reader (RapidOCR, ported from the bot)
app/tools/vision.py  One-off CPU photo analysis (Gemma 3, ported from the bot)
app/photo_jobs.py    Background /look jobs, saved progress, completion and shutdown
app/tools/image_prompts.py Reviewable AI prompt expansion and style-aware negative prompts
app/tools/imagine.py CPU DreamShaper picture worker and Quick / Good / Best presets (ported from the bot)
app/image_jobs.py    Background /imagine jobs, saved pictures, PNG downloads and popup previews
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
