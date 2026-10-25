# Making a small model feel more capable

Status: Brainstorming — not an implementation roadmap
Date: 2026-10-25

## Goal

Help a small local model, such as google_gemma-3-4b-it-Q4_K_M, deliver a more capable, consistent experience through BEYOND's context management, tools and verification. Keep ordinary chat fast and CPU operation practical. These ideas improve support around the model; they do not guarantee the knowledge or reasoning ability of a larger model.

## Feature suggestions

| Idea | Proposed behavior | Benefit and considerations |
|---|---|---|
| Think it through mode | For a difficult request, build a short plan, produce an answer, then check it against the original request. | Optional extra processing for harder questions; takes longer and needs bounded passes. A second pass alone is not reliable verification. |
| Answer checking | Verify calculations with Python, current facts through existing search tools, and document claims against source passages. | Ground answers in evidence. Distinguish checked claims from unverified ones; respect existing tool permissions. |
| Clarify before guessing | Ask one useful question when an important detail is missing. | Avoid invented assumptions, especially in troubleshooting and technical writing. Do not interrupt straightforward requests unnecessarily. |
| Conversation working notes | Keep compact notes of the current goal, confirmed facts, decisions and unresolved questions. | Improve continuity in long chats. Distinct from the existing on-demand recap: these notes support the model's active context. Define update timing, correction and deletion behavior before implementation. |
| Break down larger requests | Split a substantial request into manageable steps, complete them and combine the results into a consistent answer. | Improve completeness without overwhelming a small context window. Bound steps and provide progress/cancellation. |
| A second look button | Let the user flag a questionable answer; recheck assumptions and available evidence, then provide a corrected answer when warranted. | More useful than simple regeneration. Explain corrections and avoid treating agreement with an earlier answer as proof. |
| Code checking before delivery | Check supported generated code for syntax errors and missing pieces before presenting it. | Clearly distinguish syntax checking from actual program testing. Define supported languages; executing generated code requires a separately designed safe approach. |

## Suggested order for discussion

1. Conversation working notes: noticeable improvement in everyday continuity.
2. Answer checking: improve accuracy where tools or sources can verify claims.
3. Think it through: explicit optional mode for difficult requests.

The remaining suggestions are also candidates; this order is a recommendation, not an approved roadmap.

## Shared design principles

- Ordinary replies should not automatically incur multiple model requests.
- Extra processing should be explicit or justified by the task, with bounded time and work.
- Prefer concrete tools and source evidence over asking the same model to agree with itself.
- Preserve local operation and make any network lookup apparent.
- Evaluate improvements with representative real tasks, including latency and incorrect answers.
- Build on existing search, attachments, recaps and retry features rather than duplicating them.

## Next step

Wait for the user's instructions before selecting scope, implementation phases or a release version.
