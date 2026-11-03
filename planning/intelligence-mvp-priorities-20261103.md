# Beyond intelligence improvements: MVP priorities

Date: 2026-11-03
Based on [the evaluation report](qwen35-beyond-evaluation-report-20261103.md).

## Fix in this order

1. **Stop unnecessary web searches — [#27](https://github.com/jeremystevens/beyond/issues/27).** Questions about existing chat facts should use the conversation without an unrelated external lookup.
2. **Tighten memory recall — [#28](https://github.com/jeremystevens/beyond/issues/28).** Prevent unrelated old conversations from influencing answers; fix the deadline-wording recall cue while preserving useful recall.
3. **Verify calculations — [#26](https://github.com/jeremystevens/beyond/issues/26).** Use actual calculator results for supported numeric tasks and keep the explanation consistent with those results.
4. **Protect reference answers — [#25](https://github.com/jeremystevens/beyond/issues/25).** Treat instructions embedded inside reference material as source data, not instructions overriding the user's task.
5. **Handle missing information — [#23](https://github.com/jeremystevens/beyond/issues/23).** Say unknown when evidence is absent instead of inventing a conclusion.
6. **Follow requested formatting — [#24](https://github.com/jeremystevens/beyond/issues/24).** Respect bullets, JSON-only output, and no-introduction requests.

## First implementation batch

Implement only **#27 and #28**, then rerun the failed examples and unseen variants before proceeding. These confirmed Python defects may affect several other failures and can be fixed without adding extra model calls; broader answer-quality improvements are not guaranteed.

Keep the current model and settings for the comparison. Preserve genuine current-data searches and intentional memory recall. Do not add an extra model review to every reply or switch models as part of this first batch.

This file records priorities only; it does not mark any issue fixed or authorize a release/version bump.

## First batch status (2026-11-03)

Issues #27 and #28 are implemented and verified locally; all six acceptance items in each issue have supporting evidence. See [verification notes](context-routing-fix-verification-20261103.md) for tests, live checks and recall measurements. Publication and the closing commit are tracked in the linked issues. No release or model/settings change is included in this batch. Items #23–#26 are not claimed fixed.

## Verified arithmetic status (2026-11-03)

Issue #26 is implemented and active locally for supported budget, time/capacity, pack-price and checkout-change forms. All eight acceptance items have supporting evidence. See [verification notes](arithmetic-fix-verification-20261103.md) for supported boundaries, tests, live replies and latency. Publication is tracked in GitHub issue #26. This does not claim a general word-problem solver or fixes for #23–#25.
