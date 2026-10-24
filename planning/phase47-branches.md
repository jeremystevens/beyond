# Phase 47: Conversation branches

Status: built on 2026-10-24. From item 1 of [post-v1-feature-brainstorm.md](post-v1-feature-brainstorm.md); part of
the next release (1.1.0). The choices below were agreed with Jeremy before building.

## Goal

Try another direction from any point in a conversation without losing the original. Example: plan a vacation, then
branch from the answer about destinations to explore camping in one chat and hotels in another.

## What the user sees

- **Branch from here:** a ⑂ button in the quiet line under **any** AI answer, not just the newest. It makes a new chat
  holding the conversation up to and including that answer, opens it, and is ready for the next message. The newest
  answer in the branch has 👍 👎 🔄 ✨ as usual.
- **Name:** "*Original title* (branch)". Rename it with ✎ like any chat.
- **Finding your way:** the branch starts with a note, *"⑂ Branched from 'Vacation plans' · Open original"*. If the
  original was deleted, the note says so. Branches have a ⑂ mark in the chat list.
- **Independent from then on:** each chat goes its own way. Deleting one never deletes the other.

## What's copied

| Copied | Not copied |
|---|---|
| Your messages and BEYOND's answers up to the branch point, with their times, lookups, stats, pictures and notes | Ratings, the buttons under older messages, read-aloud audio, games (their live state belongs to the original), pictures still being made |

Memories and house rules apply to every chat, so they apply to branches too. Attachments (Phase 48) will be copied with
their messages.

## Details

- **Database:** additive only, so an older BEYOND can still read it after a rollback. `chats` gets `branched_from`
  (the original chat's id) and `branched_at` (the answer it branched from). `messages` gets `copied_from` (the
  original message's id). They're added with `ALTER TABLE … ADD COLUMN` on start-up, like earlier columns.
- **Memory recall:** a branch holds copies of the original's messages, so recall would find the same exchange twice.
  Recall now skips a copy while its original still exists, and skips an original whose copy is already part of the
  conversation being answered.
- **API:** `POST /api/messages/{id}/branch` returns the new chat. Only AI answers (`kind = 'chat'`) can be branched
  from. Anyone who can chat can branch, like Try again.

## Steps

| Step | Done when |
|---|---|
| Database, `chats.branch`, the API and recall | Tests cover what's copied and what isn't, the branch point's buttons, names, the note's data, refusing questions, commands and retried answers, deleting either side, and recall not repeating exchanges |
| The page: ⑂ button, the note at the top, the list mark | Works on desktop and phone, light and dark |
| Real check | Branch in the real BEYOND, continue both chats differently |
| Docs | README, User Guide, CHANGELOG, phases.md |
