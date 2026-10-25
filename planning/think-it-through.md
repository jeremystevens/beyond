# Think it through and compact composer tools

Status: implemented for testing; unreleased after 1.2.0
Date: 2026-10-25

## User flow
The composer keeps +, a flexible message box and Send on one row on both desktop and mobile. Popup icons and labels share a left-aligned column. The + popup contains Attach photo or document, Voice input, Writing helper and the Think it through checkbox. Existing tools keep their own handlers and optional-feature requirements. The popup supports Escape, outside click, labelled keyboard navigation and comfortable mobile touch targets. An active recording keeps a visible Stop recording control even with the popup closed.

The checkbox is off by default, remembers the preference on this browser/device, and applies to subsequent ordinary chat questions until disabled. A quiet Think it through: On control remains visible and can turn it off. The setting is independent of conversations and other devices. `/think <question>` requests the mode once, without changing the checkbox. `/think` alone explains usage and appears in /help and command autocomplete. Existing tools, slash commands and direct runtime lookups keep their own paths; this mode does not grant additional permissions or replace their workflows.

## Guided processing
1. Produce a brief checklist of requirements, constraints and important unknowns.
2. Draft an answer against that checklist and supplied context.
3. Review for all explicit requirements, practical omissions, disproportionate allocations, arithmetic and limits. Stream the improved answer and a brief Final check for planning/budget tasks, including totals and remaining money where applicable. Prices are estimates unless actual source evidence exists.

Only progress labels and the final answer are shown. Intermediate checklist/draft text is not saved as chat messages, notes or memories. Stopping cancels active model work and prevents later passes. Errors preserve the saved question for existing retry recovery; mode metadata survives retry and branches. Partial final replies keep the existing stopped/incomplete behavior.

Normal chat adds no preparatory model calls. Guided replies take longer and use the same configured model; no new model, dependency or GPU mode is introduced. The checkbox does not change the engine's separate native-thinking setting. Existing automatic lookups, if applicable, run through the normal settings-controlled path; the guided passes do not run additional tools. Multiple passes are not independent factual verification—use Check answer for evidence checks.

Recent context, checklist and draft sizes are bounded. Built-in contexts below 2,048 tokens are rejected with an explanation. Oversized current questions are rejected rather than silently cut; older context may be selected/shortened. The external-server budget follows the app's existing 8K assumption, so its configured server must have sufficient context. This does not extend a model's actual context capacity. Saved timing covers all guided passes; token count and writing speed describe the final answer.

## Validation
Focused backend checks cover the normal single-stream path, two preparatory requests plus a final stream, no saved drafts, one-question slash use, failed-prompt retry, cancellation, context limits and branch metadata. Browser coverage exercises the real composer, mobile layouts, persistent toggle/one-off behavior, recording visibility and attachment access. Existing writing-helper checks are updated to open the + popup.

README, user guide, API reference, changelog and brainstorm index are updated. Full Windows/Python 3.14 and Chromium CI must pass before merge. Release version and phase remain unchanged.

## Arithmetic evidence
For explicit dollar budgets and unambiguous flat labelled cost lists, Python sums recognized costs using Decimal and supplies that evidence to review. The final answer receives a separate program-written Calculator check, including the recognized sum, limit and remaining/overspent amount. This overrides conflicting model sums for those items. Ranges, mixed nesting and unsupported formats are declined; completeness and prices are never claimed verified. No additional model pass or external request is added.
