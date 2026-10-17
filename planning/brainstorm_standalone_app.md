# Brainstorm: BEYOND, a standalone app built from PromptetheusBot (no Telegram)

**Date:** 2026-10-17
**Status:** brainstorming only. Nothing has been built, and nothing in `promptetheus-bot` or
`Uncensored-Local-Studio-main` has been changed for this.

**Name (decided 2026-10-17): BEYOND**, short for **B**uilt **E**ntirely on **Y**our **O**wn **N**etwork & **D**evice.
Tagline: *"BEYOND: what Local AI Studio users wanted next."* Chosen so Studio users see at a glance that it goes
further than Studio, while the name stands on its own if BEYOND runs its own engine. Kept separate from
"Promptetheus" so the Telegram bot and this app aren't confused in one repo. Folder: `D:\AI\beyond`.
Avoided: "LocalAI" as one word (an existing project), names that sound like an official Studio upgrade
("Studio Plus/Pro/2.0"), and "AI Studio" on its own (Google's product).

---

## 1. The idea

Turn PromptetheusBot into a **standalone app** that you chat with in its own window instead of through Telegram.

- It keeps the same **slash commands** and all the features already built (the "mods").
- The existing Telegram bot stays **exactly as it is**. This would be a separate version.
- The point is to **share** a capable local assistant with other people. Local AI Studio is good at loading a
  model and chatting with it, but it hasn't added much in a long time: load a model and chat, play
  text-to-speech, or make an image (which rarely turns out well).

## 2. Who it's for

People who already have a computer good enough to run local AI (the kind of PC that runs Local AI Studio) and
want much more than "load a model and chat".

## 3. Decisions so far

| Topic | Decision |
|---|---|
| Chat window | A **web interface** (a local page in the browser), not a chat tab inside the CustomTkinter Control Center. A web page handles chat bubbles, buttons, pictures, drag-and-drop photos and voice far better. |
| Models | **Not included** in what we share. People download them themselves, ideally with a **download script** we provide. |
| Telegram-only features | **Left out** (see section 6). |
| Telegram bot | **Stays intact**, unchanged. |
| Network access | **Setting: "Allow other devices on my network".** On for the owner (only person on his network, so other home devices like a phone can use it); **off by default** in the shared version. Only BEYOND's own page is ever opened up, never the engine's or Studio's ports (no security on those). A login or password comes before sharing. (Decided 2026-10-17.) |
| Engine | **Undecided, leaning toward our own:** run llama.cpp directly and build our own web UI, instead of depending on Local AI Studio (see section 4). |

## 4. Options considered

### 4a. Build the features into Local AI Studio
- Studio is **MIT-licensed** (by Tech Jarves), so modifying and sharing it is allowed (keep their license notice).
- Its web page source is included (JavaScript/Vite), but it has **no plugin system**. Changes would mean editing
  its code directly, mostly a ~7,200-line server file (`scripts/server/serve.cjs`).
- Moving the features into Studio itself would mean **rewriting the whole bot from Python into JavaScript**:
  months of work, throwing away tested code. Rejected.
- Adding a "BEYOND" tab to Studio, with the Python brain running behind it, works. But it means
  maintaining **our own modified copy of Studio** and merging every Studio update by hand.

### 4b. A companion app for Local AI Studio
- Our own web app; Studio stays the AI engine (like the bot today).
- Easy for Studio users: no model downloads, no hardware setup. It uses whatever model they loaded.
- Could reuse Studio's own text-to-speech, speech-to-text and image API, so fewer downloads are needed.
- **Risks:** it relies on Studio's internal controls (load model, status), which aren't an official interface
  and could change in an update. And if Studio is abandoned, users are stuck on aging software.

### 4c. Our own engine and our own web UI (current favorite)
- The app runs **llama.cpp** itself (MIT-licensed; official Windows builds for processor, Vulkan and CUDA are
  on GitHub with fingerprints).
- **Gains:** no dependence on Studio, full control of engine settings, one app with one look.
- **Already halfway there:** `/look` and `/imagine` already run llama.cpp and stable-diffusion.cpp directly,
  without Studio. Only chat still goes through it.
- **Takes on:** downloading and updating the engine, choosing processor vs graphics card, a Models page
  (download, load, unload), and the model download script.

### 4d. Best of both (suggested)
Give the app two ways to get its AI:
1. **Built-in engine (default):** the app starts llama.cpp itself with good settings.
2. **Connect to an existing server:** for people who already run Local AI Studio, LM Studio or Ollama. They
   paste its address. The bot already uses the standard "OpenAI-compatible" chat format these share.

Keep everything engine-related in **one small "connector" piece**, so a change in any engine is fixed in one place.

## 5. The key design idea: one brain, two doorways

- **Brain:** commands, memory, AI, plugins, settings. One shared copy.
- **Doorways:** Telegram, and the new web chat. Each is a thin layer that passes messages in and out.

That way the Telegram bot and the app don't drift apart, and fixes and new features land in both. Today the
bot's code talks to Telegram directly in many places (replies, buttons, photos, voice notes), so **separating
the brain from Telegram is the first job**. It's invisible work, but it's needed for any of the options above.

## 6. What carries over

**Keep:**
- **Chat:** memory, saved facts, old-conversation search, house rules, 👍👎 learning, live typing.
- **Lookups and plugins:** automatic web, weather and news lookups; wiki, define, movie/tv, calc, convert, QR,
  time, joke, rewrite.
- **Tools:** reminders, lists, notes, expenses, morning briefing, `/scan`, `/look`, `/imagine`, `/speak`,
  voice input.
- **Games:** trivia, blackjack, quiz, tic-tac-toe, hangman, dice.
- **Housekeeping:** `/model`, `/speed`, `/restartai`, error history, `/selftest`, PC status.

**Leave out (Telegram or multi-user only):** invites, users, permissions, `/announce`, `/feedback` / `/reply`,
`/maintenance`, `/restart`. Each person runs their own copy, so they're always the "owner".

**Rethink:**
- **Owner alerts** become desktop notifications.
- **Tray icon and popups (owner's idea, 2026-10-17):** since BEYOND is a Python app, it can live in the system
  tray and pop up Windows notifications, so you can do something else and still see when **the AI has replied**,
  **a picture or photo answer is finished**, **a reminder is due**, or **an error happened**. No popups while
  you're looking at BEYOND's page; each kind can be switched off; quiet hours; clicking a popup opens that message.
  (Planned in `phases.md`, Phase 20, with Phases 22 and 23 adding "done" popups.)
- **Reminders and the morning briefing** need the app running in the background (a system-tray icon).
- **Buttons under messages** become real buttons in the web chat.
- **Photos** come in by drag-and-drop or a 📎 button; **voice** by a microphone button and audio player.

### Games need reworking for the web (noted by the owner, 2026-10-17)

Most games were built around Telegram: tap buttons under a message, and the bot edits that message to show the new
state. None of that exists in a web page, so each game's screen has to be rebuilt.

| Game | Telegram parts to replace |
|---|---|
| Trivia | answer buttons, category picker, editing the question message |
| Blackjack | Hit / Stand buttons, the table redrawn by editing the message |
| Quiz (`/quizme`) | answer buttons, Next / Stop |
| Tic-tac-toe | the 3×3 board made of buttons, difficulty picker |
| Hangman | the gallows picture swapped by editing a photo, the A–Z letter buttons, category / difficulty pickers, hints |
| Games menu (`/games`) | menu buttons |
| Dice (`/roll`) | text only, so little to change |

**Good news (checked 2026-10-17):** the game rules live in `plugins/trivia.py`, `blackjack.py`, `quiz.py`,
`tictactoe.py` and `hangman.py`, and none of them import Telegram. All the Telegram parts (14 kinds of game buttons,
message editing, Hangman's pictures) are in `bot.py`. So the **rules, scores and stats can be reused as they are**;
only how each game is **shown and played** needs rebuilding.

**Chance to make them better:** a web page can show a real tic-tac-toe grid, playing cards, a hangman drawing that
updates in place, an on-screen keyboard, and small animations, which Telegram's buttons can't do.

## 7. Model download script (if we run our own engine)

- Download **only from official sources** (Hugging Face for models, GitHub for llama.cpp).
- **Check every file's SHA-256 fingerprint.** The old thumb drive silently corrupted three models (Gemma,
  Qwen3-4B, DarkIdol). `download_assets.ps1` already works this way for the voice files.
- **Resume broken downloads**, and **check free disk space** first, showing sizes before downloading.
- **Presets by PC:**

  | PC | Suggested setup |
  |---|---|
  | 8 GB memory, no good graphics card | small chat model (~2 GB); `/look` and `/imagine` off |
  | 16 GB memory (like the MSI) | Qwen3-4B chat, Gemma 3 4B for `/look`, DreamShaper for `/imagine` |
  | good graphics card | same models, set up to use the card |

- Extras like voice, photo understanding and image generation can be ticked on or off, so nobody downloads
  10 GB they don't need.
- Some models need the maker's terms accepted on Hugging Face (Meta Llama, Google Gemma). The script should
  show the license link rather than work around it.
- Python and the libraries are installed by the same setup.

## 8. Ideas to make it clearly better than Local AI Studio

- **Image generation that works:** presets like Quick (~1 min), Good (~3–5 min) and Best (~9 min) instead of raw
  settings (measured on the MSI's processor: 256/8 steps ~1 min, 384/12 steps 3.6 min, 512/15 steps 9.2 min).
  Plus a **prompt helper** that turns a short idea into a detailed prompt, and the usual "avoid this" words
  (blurry, extra fingers…) added automatically.
- **Processor by default, graphics card as a tested option.** The MSI's NVIDIA card crashed every engine
  (Vulkan and CUDA), so we can't assume a card works.
- **Settings tuned for speed.** On the MSI, 12 threads with an f16 memory format read chat prompts about twice
  as fast as Studio's first setup.
- **No console-window surprises.** Studio froze when its console window was in "Select" mode. An app that
  runs its engine in the background avoids that.

## 9. Practical points

- **Ports:** the web page needs its own port, away from Studio's 1420, 8080 and 10086, in case both are running.
- **Naming and courtesy:** if it works with Studio, make clear it isn't official (the tagline says "what Local AI
  Studio users wanted next", not "the next Local AI Studio"). Telling Tech Jarves about it would be a nice touch.
  Before publishing, check that "BEYOND" isn't already taken on GitHub and PyPI or by a well-known AI product.
- **Licenses:** keep the MIT notices of llama.cpp, stable-diffusion.cpp and anything else we use. Model licenses
  belong to each model's maker.
- **Keep the Telegram bot and the app on the same brain**, so they don't need two sets of fixes.

## 10. Possible order of work (when we decide to build)

**Superseded by `phases.md` (2026-10-17):** 43 small phases in 7 stages, each with a "Done when" check. That plan
starts with a working browser chat inside `D:\AI\beyond` and copies the bot's Telegram-free code in, leaving
`promptetheus-bot` untouched. The original outline below is kept for reference.

1. **Separate the brain from Telegram** inside the bot (no visible change; the Telegram bot keeps working).
2. **Web chat page** using that brain, for the owner first, next to Telegram.
3. **Built-in engine** (llama.cpp started by the app), keeping "connect to an existing server" as an option.
4. **Models page** (download, load, unload) and the **setup / download script**.
5. **Package for sharing:** installer, first-run setup, README for new users.

## 11. Open questions

- Engine: our own llama.cpp (4c), companion to Studio (4b), or both (4d)?
- Should the app and the Telegram bot share the **same memory and history**, or stay separate?
- Would both run **at the same time** on one PC?
- How will it be shared: a GitHub page, a zip, or an installer?
- Voice input in the browser (microphone) or only typed chat at first?
