# Phase 33 test checklist: the built-in engine

Tick each box as you go. Everything here uses **BEYOND's built-in engine** (Settings → AI engine → "BEYOND's built-in
engine"), with Qwen3-4B-Q4_K_M and the CPU `llama-server.exe` from Local AI Studio's folder.

PromptetheusBot and Studio's own engine can stay running; BEYOND never touches them. If something goes wrong, note
what you saw. The engine's messages are in `data\engine.log`, BEYOND's in `data\beyond.log`.

---

## 1. Starting and status

- [ X] Quit BEYOND from the tray, then start it again. The status line shows **"AI engine starting…"**, then
      **"AI connected · Qwen3-4B-Q4_K_M"** once the model is loaded.
- [X ] Settings → AI engine shows **"Engine running: Qwen3-4B-Q4_K_M"**.
- [X] Task Manager → Details shows one extra `llama-server.exe` for BEYOND (the bot's own engine is the other one).
- [X] Quit BEYOND from the tray: BEYOND's `llama-server.exe` disappears within a few seconds, and the bot's stays.
- [X] Run the tests: `.\.venv\Scripts\python.exe -m unittest discover -s tests`. All pass.

## 2. Chatting

- [X] Say hello. The answer streams in **without any thinking text** (no "Okay, the user…" and no `</think>`).
- [X] Ask a follow-up that needs the earlier message ("what did I just ask you?"). It remembers.
- [X] Ask for something long, press **Stop** partway. It stops, and the next question still gets an answer.
- [X] **🔄 Try again** on an answer gives a different one.
- [X] Ask a second question straight after the first. The second answer starts noticeably faster, because the
      prompt cache works.
- [X] Open BEYOND on your other PC or phone (`https://…:7771`) and chat there too.

## 3. Memory, rules and learning

- [X] `/remember my favourite colour is green`, then in a **new chat** ask "what's my favourite colour?"
- [ ] Mention a fact in passing ("I just got a new dog named Rex"). **🧠 Noted for next time** appears.
- [X] `/rule Always answer in under 2 sentences`. The next answers follow it. Then remove the rule with `/rules`.
- [X] Give an answer **👎 → Too long** twice. `/learned` shows that BEYOND will keep answers shorter.

## 4. Lookups

- [X] "Do I need an umbrella in San Carlos tomorrow?" The answer ends with **🔎 Looked up: …**.
- [X] "Any news about SpaceX?" BEYOND looks up the news and answers from it.
- [X] `/web best budget mechanical keyboard`. The results show.

## 5. Commands that use the AI

- [X] `/rewrite polite I can't make it tomorrow`
- [X] `/joke cats`
- [X] `/quizme 7 times table`. The questions are written by the AI, and the answers check correctly.
- [X] `/imagine a cat in space` → **Improve prompt**. The improved description appears (you don't need to make the
      picture).

## 6. Photos and voice (they run beside the engine)

- [X] Attach a photo → **Describe it** (`/look`). It finishes, and chat still works while it runs.
- [X] 🎤 Say a short question. It's turned into text and answered.
- [X] **Read aloud** on an answer plays it.

## 7. Settings changes

- [X] Change **CPU threads** to 8 and press Save. The status shows "Starting…" again, then "Engine running". Put it
      back to 12.
- [X] Turn on **Let thinking models think first** and Save. After the restart, answers take longer, but still
      **show no thinking text**. Turn it off again.
- [X] Switch to **An AI server I already run** (`http://127.0.0.1:10086`) and Save. BEYOND's `llama-server.exe` closes,
      and chat answers through Studio's engine. Switch back to the built-in engine and Save; it loads again.
- [X] Type a wrong model path and Save. Settings explains that it can't find the model file, and chat shows a clear
      message instead of crashing. Put the right path back.

## 8. When things go wrong

- [X] In Task Manager, end BEYOND's `llama-server.exe`. Within about 10 seconds it's started again by itself (status
      goes "AI engine stopped" → "starting" → connected), and a popup says the engine stopped.
- [X] End `pythonw.exe` (BEYOND) in Task Manager instead, so its engine is left behind. Start BEYOND again. The
      leftover engine is closed, and only one BEYOND engine runs.
- [X] **Restart engine** in Settings restarts it and chat works afterwards.

## 9. Done when

- [X] With Studio's engine **not** used by BEYOND, chat works start to finish through BEYOND's own engine.
