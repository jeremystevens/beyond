# Context routing MVP: verification for issues #27 and #28

Date: 2026-11-03 (Pacific time).

## Status

Implemented and verified locally on MSI. All six acceptance items in each issue have supporting evidence. Publication and the closing commit are tracked in GitHub issues #27 and #28. No release or version bump is included.

The baseline evaluation report remains a historical record. This note records the first implementation batch from [the MVP priorities](intelligence-mvp-priorities-20261103.md).

## Changes

- Automatic web intent is checked against the question being searched, rather than freshness words anywhere in the message.
- Recognized correction/edit instructions do not add current-public-data intent, including when placed before the question.
- Automatic detection honors explicitly supplied-reference/current-chat context. Explicit slash and natural web-search requests still reach their existing command handlers.
- Bare deadline “before” no longer lowers the old-conversation recall relevance threshold. Conversational forms such as “what did we discuss before?” remain recognized.
- Recalled text retains chat/date and user/assistant attribution, and now explicitly labels past assistant replies as unverified claims, giving current supplied facts priority.
- No model call, dependency, migration, setting or persona change was added. The default/custom base prompt files were not edited; the application-generated recall note intentionally changed.

## Test evidence

- Original code reproduced the failures in the new regression tests before the fixes were applied.
- First broader run: **51 tests passed in 325.524 seconds**, covering context routing, memory, unknown-name lookups, weather intent, follow-ups, natural requests/routes, branches and search history.
- Expanded acceptance run initially caught a regression: a real latest-release question followed by “use the latest corrections” was suppressed. The implementation was corrected.
- Final acceptance run: **31 tests passed in 119.518 seconds**, covering the expanded context/provenance checks, actual ASGI chat route, unknown-name lookups and prior weather regression tests.
- Counts overlap; these are not 82 distinct tests. The full project suite was not run and no PR was opened.
- The first broader run emitted existing notification-worker warnings against a temporary test directory in branch tests; unittest still completed OK. The final focused acceptance run passed.
- git diff --check passed. VERSION, app/config.py and dependency files have no changes.

## Issue #27 acceptance

- [x] Exact third turn and natural paraphrases use existing chat evidence, with no lookup/network call.
  - Real-model three-turn reproduction after restarting the application returned the correct records.
  - No lookup event or stored lookup occurred on any turn.
  - Unit variants cover newline/suffix instructions and correction/edit instructions before the question.
- [x] Reply instructions such as “latest corrections” do not supply current-data intent to an otherwise unrelated question.
  - QuestionScopeTests covers latest/most-recent/current/newest instruction variants.
- [x] Quoted/reference facts and follow-up context do not accidentally become public search requests.
  - Supplied-reference/current-chat detector controls pass.
  - A reference saying “The current indicator is blue” passes through the actual stream route with lookup execution patched to fail if invoked.
- [x] Actual current public facts, e.g. latest public release details, still route correctly.
  - Latest Python release, exchange-rate, football-result and public reference-manual questions retain web intent.
  - A current-release request invokes the actual lookup route with a stand-in provider result.
- [x] Explicit /web and explicit user requests to search remain honored.
  - Both /web and “Search the web for…” reach stand-in command handlers without inference.
  - Existing explicit-search follow-up checks also passed in the broader suite.
- [x] Route-level tests assert no search function invocation, not only a correct final answer.
  - Mock assertions reject any unwanted lookups.run invocation.
  - Event and stored-message assertions additionally check lookup absence.

These are regression checks for supported patterns, not a claim that every possible natural-language source constraint is understood.

### Exact live result

Prompt sequence is the original issue reproduction: A red/pin 4 and B green/pin 7; correct A to blue and B to pin 9; then ask “What color and pin does each case have now? Use the latest corrections.”

Final answer:
> Case A is blue with pin 4, and case B is green with pin 9.

Final turn: 16.42 seconds. First two turns: 63.78 and 31.33 seconds, including first-use/context costs after restart. These samples are not a general speed benchmark.

## Issue #28 acceptance

- [x] “before Monday/Friday/5 pm” does not independently indicate old-conversation recall.
  - Explicit cue tests cover all three forms.
- [x] Unrelated one-keyword fixture produces no history for both deadline variants.
  - In-memory Monday-lunch fixture returns no exchange for “before Monday” and “on Monday”; a longer deadline variant also passes.
  - Controlled pre-fix replay retrieves one irrelevant exchange; fixed replay retrieves zero.
- [x] Explicit references to past conversations still retrieve relevant exchanges.
  - Remember/recall/discuss-before/mention-before controls pass.
  - The live engine identifies the sandwich in both repeats using the fixed recalled context.
- [x] Ordinary queries with genuinely sufficient topic overlap retain useful automatic recall.
  - “Monday lunch ideas” retains its relevant exchange.
  - Existing branch recall/deduplication tests passed in the broader suite.
- [x] Include source provenance and distinguish old assistant claims from verified facts; do not broadly suppress all memory.
  - Tests verify date, chat title, user/assistant attribution, explicit unverified-claim wording and current-fact priority.
  - Relevant retrieval remains enabled; skip IDs and negatively rated-answer exclusion remain supported.
- [x] Evaluate CPU prompt size/latency and answer quality with relevant versus irrelevant recall.
  - Eight controlled samples replayed pre-fix and fixed recall blocks generated from the same isolated fixture.
  - Same existing CPU model, active system-prompt hash and default temperature; 120-token output cap per measurement; two runs per condition in forward/reverse order.
  - No production chat, fact, rating or setting was changed by these isolated replay probes.

### Recall measurement results

| Query/context | Before: exchanges / background chars / prompt tokens | After: exchanges / background chars / prompt tokens | Before mean wall time | After mean wall time |
|---|---|---|---:|---:|
| Parcel deadline with unrelated Monday-lunch history | 1 / 286 / 1353 | 0 / 0 / 1271 | 11.85 s | 7.24 s |
| Explicit recall of the Monday lunch | 1 / 286 / 1354 | 1 / 401 / 1373 | 11.02 s | 11.58 s |

Measured CPU prompt-processing means: irrelevant context 6.05 to 2.69 seconds; relevant context 6.46 to 7.35 seconds. The irrelevant exchange is removed, saving 82 total input tokens in this fixture. The clearer provenance note adds 19 tokens when relevant recall is retained.

Core answer quality was retained in all eight probes: parcel timing remained unknown without shipping evidence, and lunch recall correctly identified the sandwich. This small fixture did not demonstrate a general quality improvement. Some replies still added unnecessary follow-up wording, including one irrelevant /memories suggestion; those are outside these two routing fixes.

Two samples per condition do not establish a reliable speedup or slowdown. Cache state, sampling, different answer lengths and other CPU work affect wall time. Raw usage, prompt-processing/generation timings and replies are retained for review.

## Final running state

- HTTP: 200.
- Trusted HTTPS, verified hostname beyond.ddns.net over loopback: HTTP/1.1 200 OK.
- Engine: ready/idle, Qwen3.5-4B-Q4_K_M.gguf.
- Saved settings fingerprint matches the pre-change snapshot.
- No saved facts were added since the source backup.
- The user's chats were preserved. Only the newly created three-turn verification chat was deleted.
- Browser Portal, Caddy and Promptetheus were not restarted.
- Base prompt/model settings, versions and dependencies remain unchanged.

## Files and local evidence

Source/test changes:
- app/lookups.py
- app/memory.py
- tests/test_context_routing.py
- tests/test_natural_tool_routes.py
- README.md and CHANGELOG.md

Ignored verification directory: data/context-routing-fix-20261103/
- before.zip: original affected source/docs.
- before-tests.log: pre-fix regression failures.
- focused-tests.log: 51-test broader pass.
- acceptance-tests.log: caught intermediate regression.
- acceptance-tests-final.log: final 31-test pass.
- live-verification.json: exact live three-turn result and event types.
- recall-measurements.json: eight recall probes with usage/timings/raw answers.
- final-state.json: ready/idle, unchanged settings and HTTP/TLS results.
- settings.sha256: original saved-settings fingerprint.

Issues: [#27](https://github.com/jeremystevens/beyond/issues/27), [#28](https://github.com/jeremystevens/beyond/issues/28). Other evaluation issues #23–#26 have not been claimed fixed.
