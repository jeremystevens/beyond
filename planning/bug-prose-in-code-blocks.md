# Bug: prose appears as Python code

Reported by Jeremy on 2026-10-26 with a screenshot. Status: fixed; further testing needed. The reported case is live-verified; unreleased after 1.2.0.

Reproduction: in a chat, ask "Give me a generic polite email template declining an invitation". BEYOND provided an email, then invented Python blocks containing formal/informal /rewrite demonstrations and email prose. The Python checker correctly rejected this invalid Python. The bug is unwanted model output/formatting, not evidence that the checker executed the email.

Expected: give the requested email as ordinary text. Do not invent helper code or rewrite-command demonstrations. Preserve fences, language labels, Copy/Save and syntax checks for actual requested code. Honor explicitly requested literal text blocks.

Fix: make prose-versus-code boundaries explicit in the shared app contract and default personality, and reinforce them in writing-task help. Do not strip arbitrary fences or silently rewrite model output; a request may legitimately include both prose and code. Shared instructions apply alongside custom prompts; no saved custom prompt or live model setting is edited.

Validation must exercise the full chat request, including command catalog and writing-task notes, plus a genuine Python request and a mixed prose/code request. Earlier isolated model checks missed this live-chat problem. No release version changes.

## Validation, 2026-10-26

All 26 targeted prompt, Python syntax-check and rewrite/helper tests passed. Whitespace validation passed. Restarted only the verified BEYOND process to load the updated instructions; model/settings stayed unchanged.

The live /api/chat/stream path was tested with Llama-3.2-3B-Instruct-Q4_K_M, normal chat mode, existing full command catalog, feature notes and runtime context:

- Exact reported sequence: "Reply to this email", followed by "Give me a generic polite email template declining an invitation." The first turn asked for the missing email; the second returned email prose only, without helper scripts, rewrite demonstrations or fences.
- A short thank-you letter returned plain text without fences.
- An actual Python add-two-numbers example retained its python fence, indentation and explanation. The code was not executed.
- No stream errors; only newly created synthetic chats were deleted after the checks. Local raw results remain in ignored dist/prose-code-bug-live.json.
- Jeremy saw the two writing tests live and confirmed that the issue looks fixed.

This fixes the reported reproduction. Model instruction adherence can still vary, especially with conflicting custom prompts or unusual requests; no general prose-to-code heuristic strips or rewrites user-requested code. Release version and root VERSION remain unchanged.

Owner status decision: mark this bug fixed, with further testing needed across more writing requests, models and custom prompts before broader confidence claims.

Pre-push verification: the optional full discovery run was interrupted because it was progressing very slowly on the working PC; it is not recorded as passed. It logged Windows popup registration permission errors. Focused regression checks and the live reproductions are the validation basis for this fix; broader testing remains explicitly required.

Final pre-push result: all 57 focused tests passed together across clarification matching, natural requests/routes, guided replies, prompt transport, Python syntax checks and rewrite/helper behavior. Git whitespace validation passed.
