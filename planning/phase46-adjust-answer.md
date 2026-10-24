# Phase 46: Adjust this answer

Status: built on 2026-10-24. From item 5 of [post-v1-feature-brainstorm.md](post-v1-feature-brainstorm.md); part of
the next release (1.1.0).

## Goal

Get a better follow-up to an answer without typing a new prompt. Under the newest AI answer, a ✨ **Adjust** button
opens four choices:

| Choice | What BEYOND does |
|---|---|
| **Simpler** | Explains the same thing again in shorter sentences and everyday words |
| **More detail** | Expands the answer with useful detail, not padding |
| **Show an example** | Gives a concrete example (a short code block when the answer is about code) |
| **Walk me through it** | Turns it into numbered steps |

## How it works

- **Where it appears:** in the quiet line under an AI answer (copy, 👍, 👎, read aloud, 🔄), only on the **newest**
  answer, like Try again. Command replies, games and notes don't get it.
- **How the result joins the chat:** the choice is saved as your message ("Simpler, please", "More detail, please",
  "Show me an example", "Walk me through it"), and BEYOND answers it below like any reply, with its own stats, rating
  and Adjust. The original answer stays as it was, so you can compare them, and the conversation reads naturally
  when you scroll back or reopen it.
- **What the AI is told:** the normal conversation history, plus a short note for that one reply: what was asked,
  to rework *its previous answer* accordingly, to keep everything that was correct, and not to apologise or mention a
  button. No extra AI call, so it costs one normal reply on a CPU.
- **No surprises:** an Adjust reply never starts a web lookup or file action by itself (it's about the answer that's
  already there). Fact pickup ("🧠 Noted") is skipped too, because the message is a button press, not something you
  said about yourself.
- **Safety:** the server only accepts the four choices, and only for the newest AI answer in that chat. Everyone who
  can chat can use it, like Try again.

## Steps

| Step | Done when |
|---|---|
| `POST /api/messages/{id}/adjust` with `kind` = simpler, detail, example or steps | Tests cover each choice, the saved message, the note sent to the AI, no lookups, and refusing old answers, commands and unknown choices |
| ✨ Adjust button and menu on the page | Shows on the newest answer only, moves to the new answer, works on phones and in light and dark |
| Real-model check | Each choice gives a sensible reply with the 4B model on this PC |
| Docs | README, User Guide and CHANGELOG |
