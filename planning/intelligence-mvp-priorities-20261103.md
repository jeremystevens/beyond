# Beyond intelligence improvements

Updated November 4, 2026. See the [evaluation report](qwen35-beyond-evaluation-report-20261103.md) for the original test cases.

## Complete

| Issue | Result |
| --- | --- |
| [#27](https://github.com/jeremystevens/beyond/issues/27) | Corrected automatic lookup routing for conversation facts and reply instructions. |
| [#28](https://github.com/jeremystevens/beyond/issues/28) | Corrected deadline-triggered recall and labeled recalled replies as unverified. |
| [#26](https://github.com/jeremystevens/beyond/issues/26) | Verified supported budget, time, capacity, pack-price, and checkout calculations locally. |

See the [routing and recall verification](context-routing-fix-verification-20261103.md) and [arithmetic verification](arithmetic-fix-verification-20261103.md).

## Improvements shipped with follow-up work open

| Issue | Verified scope | Remaining work |
| --- | --- | --- |
| [#25](https://github.com/jeremystevens/beyond/issues/25) | Quoted reference checks and 12 attachment and lookup cases for supported capacity, duration, and weight questions. | Verify external-source questions outside the supported forms. |
| [#23](https://github.com/jeremystevens/beyond/issues/23) | Explicit supplied-facts requests skip unrelated recall, feedback, and lookup. The original delivery prompts and explicit late-arrival case passed on the loaded model. | Recheck stock and conflicting-source reasoning, and verify with Qwen3.5. |
| [#24](https://github.com/jeremystevens/beyond/issues/24) | Explicit format guidance, bounded wrapper cleanup, and verified two-option budget bullets. Twenty-seven focused tests passed. | Repeat the formatting checks on a second model. |

Detailed evidence and acceptance checklists are tracked in the linked issues.
