# Answer checking

Status: implemented; unreleased after 1.2.0
Date: 2026-10-25

## Goal and interface
Help a small local model with independent calculations and visible source evidence. Ordinary chat adds no checker requests or model passes.
Open the existing Adjust answer icon under a saved AI reply, then choose Check answer. This uses the existing menu rather than adding another permanent reply icon. Controls live in a themed, scrollable dialog with full-width fields and 44 px phone touch targets.

## Delivered scope
- Calculator: enter an expression or equation, such as `15% of 80 = 12`. A simple parseable equation in the answer is suggested automatically. The safe existing Python calculator evaluates it without executing generated code, calling the model or using the network. Matches use relative tolerance 1e-9 and absolute tolerance 1e-12; only the selected expression is checked.
- Attached documents: select a specific claim (up to 2,000 characters), retrieve passages from this chat's attachments and make one bounded model assessment. File/page evidence remains visible. Selected passages do not establish what omitted passages say.
- Public web search: the user enters a query (up to 300 characters) and explicitly presses Search and check. Only that query goes to the existing search tool. Results show snippets and safe source links, with at most one model assessment. Search pages are not opened or exhaustively researched; snippets may be incomplete or wrong.
- Instructions in claims, documents and search snippets are treated as data. An AI assessment is labelled separately from calculator results and source evidence; it is not an independent guarantee.
- Original replies, ratings, chats and memories are unchanged. Check results are not persisted and are cleared when inputs change or the dialog is reopened.
- Missing sources, busy engines and search failures are explained. If model assessment fails or times out, evidence is still returned with no conclusion established. Closing cancels model work; an already-started threaded search may finish in the background.
- No new runtime dependency, automatic external lookup, model load, or release-version change.

## Validation
Focused backend tests cover correct/incorrect equations, malicious expressions, explicit-query isolation, no-result/missing-source behavior, model failure, busy state, deleted answers, source-data prompt boundaries and equation suggestions.
Browser coverage exercises the real chat menu, no checks on chat opening, literal rendering, safe links, errors, changed inputs and narrow 320/390/760 px dark layouts. Full Windows/Python 3.14 and Chromium CI passed on feature commit fc817007c856ea896e99467e08a0ac0445321b1d (Actions run 40222457154).

Live validation after restarting BEYOND confirmed that an incorrect equation is detected without AI inference, the original reply is unchanged, and the chat serves the checker menu/dialog. Only the validation chat was removed. The user confirmed the phone layout works. Documentation-only follow-up checks and post-merge main checks are required before moving on.

## Future possibilities
Automatic claim extraction, full-page retrieval, multiple-source reliability ranking, deeper mathematical reasoning, code execution and automatic corrections are outside this first increment. Conversation working notes and the other brainstorm candidates remain separate work.
