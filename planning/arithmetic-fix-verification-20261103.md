# Verified word-problem arithmetic: issue #26

Date: 2026-11-03 (Pacific time).

## Status and scope

Implemented and active locally on MSI. All eight acceptance items have supporting evidence. Publication is tracked in GitHub issue #26.

This is a bounded MVP for supported English forms: individual option costs versus a budget, recording-time remainders, whole-item shelf capacity, same-store sealed-pack comparisons, and checkout change when no tax/extra charge applies. It is not a general natural-language math solver. Unsupported/ambiguous inputs remain ordinary model chat and are not marked locally calculated.

## Implementation

- app/word_math.py extracts explicit quantities from supported user statements. Source values come from the current question or a bounded same-chat user budget history, never old assistant arithmetic or cross-chat recall.
- Every supported answer is program-written from deterministic calculations through the existing safe calculator. No model generates a plan, executes Python, drafts the numeric answer or reviews it.
- Cents and scaled integer units avoid float-floor errors such as (0.3 - 0.1) / 0.1. Unit conversions and fractions have explicit units; requested whole quantities use exact floor/ceiling arithmetic.
- Latest explicit budget corrections update every option; supplied finish days are retained or replaced when explicitly corrected.
- Missing operands, extra numeric conditions, mixed currencies, uncertain values, unsupported fees/rates, per-pair/per-item qualifiers and negated facts decline to normal chat rather than receiving a calculation claim.
- app/server.py uses the normal chat stream/storage/retry path. A transient Calculated locally status identifies this route. Messages remain normal chat for later context; model lookup and automatic personal-fact pickup are bypassed for supported calculations.
- Existing /calc, /convert, guided thinking, answer checking and unrelated prose retain their paths. A purely supported calculation does not require guided model passes even when the guided flag is selected.

## Validation

- Broader Windows regression: **82 tests passed in 350.712 seconds** across the new parser/routes, prior natural/context/weather routing, answer checking, guided thinking and follow-ups.
- Expanded route/parser run: **16 tests passed in 42.535 seconds**.
- After the last boundary rejection additions, **12 parser tests passed in 0.025 seconds**.
- Counts overlap; this is not 110 distinct tests and not a claim that the full project suite or GitHub CI was run.
- Real API after loading the final source: **8/8 turns passed**. Stored stream answers exactly match computed helper answers, with a local-calculation status and no lookup event.
- A curated coverage sample recognizes all eight supported turns and declines all seven unsupported controls. This does not estimate coverage or accuracy over arbitrary word problems.
- Unit/ASGI tests use temporary data, fake inference/providers and explicit call assertions. Supported requests actually invoke calculator.evaluate; model draft/review/fact-pickup and public lookup calls are patched to fail if used.
- Ordinary prose with numbers and unsupported math still reaches a stand-in model. Existing pending-file, command and weather behavior passed regression coverage.

### Before-fix evidence and repeat results

The historical evaluation captured the incorrect initial 90-minute claim, $180 instead of $280 remainder, and $20 instead of $70 over-budget claim. These were intermittent failures.

One additional current before-fix live recording-space request answered correctly in 34.653 seconds. The baseline batch yielded when the engine reported busy before the next case, so no further before-fix responses are claimed from that batch. Successful and failed historical examples are retained rather than describing an always-reproducible model error.

The final after-fix recording-space requests both returned 20 minutes consistently; budget replies returned $280/$80 initially and $130 remaining/$70 over after correction, preserving day 5.

## Acceptance mapping

- [x] Repeat exact and unseen variants, recording both passes and failures.
  - Historical failures and successful repeats remain in the baseline report/issue.
  - New before-fix time pass and interrupted-batch reason are preserved.
  - Eight live after-fix turns include exact prompts, a repeat, updated budget, unseen time quantities, decimal capacity, checkout and different stores/currency.
- [x] Distinguish unit conversion, initial quantity, intermediate subtotal, and final result.
  - Time answer labels 90 minutes available, 2 × 35 minutes used, and 20 minutes remaining.
  - Checkout distinguishes $7.20/$1.75 subtotals, $8.95 total and $1.05 change.
  - Capacity labels current load, added load, resulting total and the next count that exceeds the limit.
- [x] For safely supported calculations, obtain an actual deterministic result rather than merely prompting the model to claim tool use.
  - Safe-calculator call assertions and expression/result/unit traces verify execution; no LLM translates or claims execution.
- [x] Keep leading conclusion, arithmetic working and final sentence consistent with verified values.
  - Program-written output contains the computed result throughout, bypassing a fallible numeric rewrite. All eight live replies matched computed text.
- [x] Cover decimal money, unit conversions, whole-pack constraints and updated budgets.
  - Decimal cents, fractional kg/mixed g/kg, hours/minutes/seconds, round-up whole-pack costs, exact-count infeasibility and budget/day corrections pass.
- [x] Preserve normal prose and avoid dispatching every message containing a number to a calculator.
  - Clear supported task/quantity structure is required. Ordinary pets/prose, qualitative choices, incomplete/uncertain/currency-mixed or qualified prices decline. A stale unrelated user turn prevents budget carryover.
- [x] No unrestricted generated-code execution; use the existing bounded calculation facilities where appropriate.
  - Only program-built integer expressions and fixed operators reach the existing AST-whitelisted calculator. No eval/exec or generated-script execution was introduced. Input, count, amount, row and expression bounds are enforced.
- [x] Measure latency/coverage before adding review calls to ordinary CPU-only replies.
  - 800 helper measurements and eight final live API turns are recorded below. No review or extraction model call was added to ordinary chat.

## Measured latency

Helper-only CPU sample: 800 calls; mean 0.3236 ms, median 0.3145 ms, p95 0.5623 ms, maximum 1.0815 ms. This excludes request/database/UI and model time.

Final live supported requests: 1.233–1.751 seconds; median 1.470 seconds. These are small end-to-end observations under the current load, not a general speed guarantee or token-generation benchmark. The single before-fix 34.653-second time response is not a controlled multi-sample performance baseline.

| Live check | Wall time | Result |
|---|---:|---|
| reported_time | 1.567 s | Correct; calculated locally |
| reported_budget / turn 1 | 1.233 s | Correct; calculated locally |
| reported_budget / turn 2 | 1.393 s | Correct; calculated locally |
| unseen_time | 1.604 s | Correct; calculated locally |
| checkout | 1.393 s | Correct; calculated locally |
| decimal_capacity | 1.751 s | Correct; calculated locally |
| unseen_packs | 1.432 s | Correct; calculated locally |
| reported_time_repeat | 1.507 s | Correct; calculated locally |

## Final state and limits

- HTTP 200; trusted HTTPS HTTP/1.1 200 OK.
- Current engine ok, busy=false; Qwen3.5-4B-Q4_K_M.gguf.
- Saved settings fingerprint matches the pre-change snapshot.
- No version, default/custom base prompt, dependency or calculator implementation change.
- Only disposable test chats created by these checks were deleted; user chats were preserved.
- Browser Portal, Caddy and Promptetheus were not restarted.
- No price, weight limit, stock, delivery outcome or other real-world fact is independently verified by arithmetic.
- Recognition is deliberately conservative and pattern-based. Unsupported natural wording may still receive an incorrect ordinary model answer; it is not marked calculated locally. Semantic interpretation is not universally verified.
- Other issues #23–#25 are not claimed fixed. See GitHub issue #26 for publication status.

## Files and evidence

Changed/new application files: app/server.py and app/word_math.py. Tests: tests/test_word_math.py and tests/test_word_math_routes.py. Supported forms/limits are documented in README.md and CHANGELOG.md.

Ignored local evidence directory: data/arithmetic-fix-20261103/
- before.zip: original affected source/docs.
- before-live.json: correct current pre-fix time response and subsequent busy/yield reason.
- regression-tests.log: broader 82-test pass.
- final-qualifier-tests.log: 16-test parser/route pass.
- final-boundary-tests.log: last 12 parser tests.
- coverage-latency.json: recognized/declined controls, safe expression traces and helper timing.
- after-live.json: final eight live turns with status/event types and wall time.
- after-initial-live.json: earlier successful live pass before the last ambiguity guards.
- final-state.json and settings.sha256: HTTP/TLS, current engine and unchanged saved settings.

## Exact final live prompts and replies

### reported_time — turn 1

Prompt: A recording device has 1.5 hours of recording space left. Two recordings each last 35 minutes. How many minutes of space remain after both recordings? Briefly show the arithmetic.

Reply:
> 20 minutes remain: 90 minutes available − (2 × 35 minutes) = 20 minutes.

### reported_budget — turn 1

Prompt: For this fictional planning exercise, a repair costs $220 and a replacement costs $420. My budget is $500 and both options finish on day 5. For each option state whether it fits the budget, the amount remaining or over budget, and the finish day.

Reply:
> - Repair: fits; $280.00 remains ($500.00 − $220.00 = $280.00). Finishes on day 5.
> - Replacement: fits; $80.00 remains ($500.00 − $420.00 = $80.00). Finishes on day 5.

### reported_budget — turn 2

Prompt: Correction: my budget is now $350. All other facts are unchanged. Re-evaluate both options and keep their finish days in your answer.

Reply:
> - Repair: fits; $130.00 remains ($350.00 − $220.00 = $130.00). Finishes on day 5.
> - Replacement: does not fit; $70.00 over budget ($350.00 − $420.00 = -$70.00). Finishes on day 5.

### unseen_time — turn 1

Prompt: A recorder has 2 hours remaining. Three sessions each take 25 minutes. How many minutes remain? Briefly show the arithmetic.

Reply:
> 45 minutes remain: 120 minutes available − (3 × 25 minutes) = 45 minutes.

### checkout — turn 1

Prompt: I pay $10 for three items costing $2.40 each and one item costing $1.75. There is no tax or other charge. How much change should I receive? Briefly show the calculation.

Reply:
> You receive $1.05 in change: items total $7.20 + $1.75 = $8.95, and $10.00 − $8.95 = $1.05.

### decimal_capacity — turn 1

Prompt: A shelf supports 0.3 kg. It already holds 0.1 kg. Each crate weighs 0.1 kg. How many whole crates can I add? Briefly explain.

Reply:
> 2 whole crates can be added. 0.1 kg + (2 × 0.1 kg) = 0.3 kg, within the 0.3 kg limit; 3 would total 0.4 kg, exceeding it.

### unseen_packs — turn 1

Prompt: I need at least 7 pens. Shop North sells packs of 3 pens for £2.50. Shop South sells packs of 4 pens for £3. Packs cannot be split. Which shop has the lowest cost? Show packs and totals.

Reply:
> Shop South has the lowest total: £6.00.
> Shop North: 3 whole packs provide 9 items for £7.50.
> Shop South: 2 whole packs provide 8 items for £6.00.

### reported_time_repeat — turn 1

Prompt: A recording device has 1.5 hours of recording space left. Two recordings each last 35 minutes. How many minutes of space remain after both recordings? Briefly show the arithmetic.

Reply:
> 20 minutes remain: 90 minutes available − (2 × 35 minutes) = 20 minutes.
