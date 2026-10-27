# Clarify before guessing

Status: implemented and live-tested; unreleased after 1.2.0. Known small-model question-bundling limitation remains.

Selected by Jeremy on 2026-10-26. Ordinary chat should ask one short, specific question when an essential missing detail would materially change the answer. It should use the current request, recent messages and supplied context first, then wait for the answer instead of inventing details. Clear requests, generic examples and templates should proceed; optional preferences are not blockers. A useful stated assumption or placeholder is appropriate when the user delegates the choice.

## Implementation

A compact policy in app/prompts.py is included in the stable app contract for default/custom chat. After the owner reproduced an invented email reply in the real UI, added app/clarifications.py and a guard in the normal saved-answer stream. For an otherwise empty conversation, a conservative full-message match for a bare email-reply, error-fix or letter-draft request returns one app-written question without inference. It accepts simple polite wrappers but excludes supplied content, extra clauses, generic/template requests and delegated choices. Earlier conversation, document attachments, reviewed working notes, photo/source messages and file/lookup context bypass the guard. Existing commands and pending file contents retain precedence.

The app-written question is saved as an ordinary chat answer, so past intent and the clarification remain available when the user supplies the content. It uses the existing stream/save/retry lifecycle without a new database or setting. It has no fabricated model/token stats, no code block and no fact-extraction call. Think it through does not run preparatory calls when the app can ask the missing-input question itself. More nuanced ambiguity still uses the shared prompt guidance.
The model decides whether information is essential. This is guidance, not a guarantee that every small model asks exactly one question or avoids unnecessary questions. It adds a short stable prompt block and can add prompt-processing time; it does not guarantee unchanged latency. Nothing changes the release version or root VERSION.

## Acceptance cases

Use ordinary chat with Think it through off. Check actual replies, not only prompt text:

| Request/context | Expected behavior |
|---|---|
| Help me fix this error (no error provided) | One short question asking for the error message; no invented cause |
| Reply to this email (no email provided) | Ask for the original email |
| Write a letter (no subject or purpose) | Ask what the letter should say |
| Explain how rainbows form in three sentences | Answer directly |
| Give me a generic polite decline email template | Provide a template, using placeholders if needed |
| Earlier user: Python reports ModuleNotFoundError: No module named requests. Current: How do I fix this error? | Use supplied error, without asking for it again |
| Earlier assistant asks for the error. User supplies the traceback | Address that error rather than restarting the questions |
| Plan a simple weekend activity; choose the details yourself | Proceed with a reasonable stated assumption |

Repeat with a custom chat prompt and a small CPU model. Compare question selection and time to first token against the previous contract; separate cold prompt processing from warm replies. Do not change the owner's model or performance settings for acceptance. Automated transport checks establish prompt/context preservation and one-off isolation; they cannot establish model response quality.

## Verification record (2026-10-26)

All 30 targeted tests passed across test_prompts, test_natural_requests, test_natural_tool_routes and test_think_through. After the final instruction changes, all six prompt tests passed again. Git whitespace validation passed. Transport checks cover default/custom prompts, streaming/nonstreaming payloads, retained prior messages/context and unchanged one-off job instructions.

The first live comparison timed out after 120 seconds during the baseline. An initial evaluator import also encountered an OpenBLAS memory-allocation failure. At Jeremy's request, waited five minutes after his file-moving activity, then retried successfully against the already-running Llama-3.2-3B-Instruct-Q4_K_M CPU engine. No model switch, performance-setting change, app restart or other-app shutdown was performed.

Used synthetic messages with the default personality and app contract, without saved chats, personal context or the full command catalog. Temperature 0, 120-token output cap. Eight baseline cases and eight cases for each of four policy iterations were reviewed. These are policy-level checks, not full browser/route acceptance or tests of every custom prompt/model. Draft examples and template formatting are not certified by these checks. Some full answers hit the output cap.

The initial 33-word policy kept the existing 500-word budget but still invented a letter purpose. Adding concrete missing-error/email/purpose examples fixed that, but one iteration over-questioned a delegated weekend plan. Front-loading the direct-answer exception and reinforcing it corrected the delegation case. The final policy has 117 words; the default plus app contract has 583 words. The prompt regression budget is deliberately raised to 600 to retain the behavior examples that performed better; no separate model request is added.

Final live results:

| Case | Observed |
|---|---|
| Missing error | Asked for the error message/description instead of inventing a cause |
| Missing email | Requested the email content without drafting or asking for tone |
| Clear rainbow explanation | Answered directly, no clarification |
| Generic decline template | Produced a template, no clarification; unnecessary code-fence formatting remains a model limitation |
| Error already in earlier context | Used that error, no repeated request |
| User answers earlier clarification | Gave relevant advice rather than restarting questions |
| Delegated weekend plan | Proceeded with stated assumptions, no interview |
| Letter without a purpose | Asked instead of inventing a purpose, but bundled recipient and topic into one question |

The strict one-essential-detail-only rule is therefore not fully reliable on this model. Seven cases met the clarification-choice criteria; the letter case is partial. Even one grammatical question can request multiple details. Retained this limitation explicitly rather than claiming perfect compliance or leaving the feature untested.

Final total-response times ranged from 2.33 to 13.99 seconds, including varying output lengths. Baseline and later runs were sequential with different cache prefixes and changing machine load; these numbers do not establish an unchanged-latency claim. The code still sends one normal request. Raw synthetic results are retained locally in ignored dist/clarification-evaluation*/results.json.

## Owner-reported real-chat correction

The owner supplied a screenshot of a new chat with "Reply to this email" producing an invented professional letter and a spurious Python block. The earlier direct-model tests omitted real-chat feature notes, command catalog, runtime context and custom preferences; they did not establish that the complete UI request would work. The exact cause of the difference is not independently proven. Prompt-only behavior is not sufficient for known bare missing-source requests, so those now use the app-written guard above.

Route regression coverage now uses the actual /api/chat/stream endpoint with disposable data: exact reported request, saved chat kinds/content, no model/classifier call, continuation with pasted email and retained original intent, source/working-note bypass and guided-mode bypass. Separate matching checks cover supplied content, templates, negation, quoted requests, extra actions and existing history. Tests use simulated AI only for paths that should continue to normal inference; the guarded question itself is app-written.

Correction validation: 34 tests passed across clarification matching, real chat-route tests, guided mode and prompt transport. After adding the media-source bypass, the exact-email continuation and photo-context route checks also passed (2 tests). Whitespace validation passed. The running BEYOND process was not restarted; load this fix on its next normal restart and test in a new chat.

Owner-authorized live restart verification: relaunched only the verified BEYOND process to reload Python code (the Settings restart only recycles its web server). Health returned OK, and the live /api/chat/stream endpoint returned exactly "Could you paste the email or message you want me to reply to?" for the reported bare request. Removed only the newly created synthetic test chat afterward. No model or performance settings were changed.
