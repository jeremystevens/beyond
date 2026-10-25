# Conversation working notes

Status: implemented; unreleased after 1.2.0
Date: 2026-10-25

## Behavior
Working notes sits beside Recap for a saved chat. It opens an editable, themed dialog for the current goal, confirmed facts, decisions and open questions.
- Write notes manually or explicitly Draft from chat. Drafting makes one model request and does not save or enable its output. Review/edit, then Save and use.
- Active notes add at most 1,600 characters of local context to subsequent AI replies in this chat. Normal replies do not scan old history or trigger a notes-generation request. The added text can modestly increase prompt-processing time; it does not give the small model unlimited context or guaranteed recall.
- Notes are not automatically refreshed. The dialog reports newer messages since the last save. Draft again when useful; previous reviewed notes are supplied as historical reference alongside bounded conversation excerpts. Newer messages take precedence.
- Long chats use selected opening/recent excerpts, with an explicit coverage warning. AI suggestions must not become user-confirmed decisions. Model identity, PC statistics and other transient values should not be retained as live facts.
- Pause keeps the text but removes it from context. Save and use re-enables reviewed notes. Clear notes removes their text without touching messages or global memories.
- Editing/deleting a covered message clears and disables derived notes. Stale saves and drafts are rejected. Deleting the conversation cascades to its notes. A branch starts with empty, independent notes, avoiding future information leaking into earlier branches.
- Notes are stored in the existing private chat SQLite database, not global memory. Neither drafts nor saved notes are inserted as chat messages. No web lookup, added runtime dependency or model download.

## Interface and checks
The existing recap area contains the new control, leaving the composer and reply icon row unchanged. The dialog scrolls on small screens, follows the current theme and uses 44 px mobile buttons.
Backend checks cover isolation, no inference/history scan in normal context, newer turns, source invalidation, pause/clear, conflicting saves, branches, conversation deletion, draft errors and generation races. Browser checks exercise explicit generation, review/save, pause, failure preservation, clear, and 320/390/760 px dark layouts.
Full Windows/Python 3.14 and Chromium checks passed on feature commit 270fdde38dd7be9892223754e14604964df1045f (Actions run 40224748631). The documentation follow-up and post-merge main checks are validated separately. Release version and phase remain unchanged.

Live testing confirmed that the real model drafted compact notes without saving them, used a fact supplied only in notes, and respected pause/clear state. The initial request for a one-word code returned CEDAR instead of CEDAR73; an explicit request to include its digits returned the complete code. Notes improve context, not precision guarantees. Only validation chats and their notes were removed.
