# Phase 51: Screenshot troubleshooting (unreleased)

Selected by Jeremy after conversation recaps. Add a focused screenshot action using installed optional readers, with useful follow-up context.

## Behavior

- Attach/drop an image, or paste one into the message box. Reuse image validation/metadata stripping, the photo preview and its optional question/context field. A small Troubleshoot this button fits the existing photo tools; reader selection offers Automatic, Read error text (OCR), Understand screen (vision).
- Automatic chooses a verified installed OCR reader first, otherwise configured CPU vision. Explicit selection never silently switches readers. No new runtime dependency, model downloads or database migration. Missing readers explain Add-Features.cmd and pasted-text alternatives.
- Reuse the background /api/look action and its lock, progress, arrivals, popup preferences, deletion and shutdown/restart handling. OCR runs off the event loop; vision exits before the text AI is called. Neither stops the existing text engine.
- One text-model advice call after evidence extraction. Bounded evidence, low temperature and a focused prompt distinguish observations from possible causes, suggest up to three reversible first checks and ask up to two relevant questions. Screenshot content is source data, never instructions. No commands, repairs or web calls run.
- Save the user context, sanitized image and final advice/evidence in the chat. New troubleshoot message kind participates in recent conversation history and recaps so ordinary follow-ups retain context. Other OCR and vision results retain their existing behavior. Branches copy completed messages normally; pending jobs are excluded as before.
- Chat history follows its normal context window; this is not permanent model memory. OCR can misread text, vision can hallucinate and small text models can give poor advice. Evidence is visibly labeled for correction. A lack of readable text asks for clearer evidence rather than inventing a diagnosis. External text engines receive evidence when configured.

## Validation

- Eleven isolated Python checks cover OCR/vision selection, missing dependencies, evidence-based generation, saved follow-up context, arrivals, unreadable evidence, validation, failures, deletion, cancellation and busy/empty models.
- Browser checks cover attachment and clipboard preview, action/context/reader submission, result rendering/Copy, literal HTML safety, recovery after missing features, and narrow mobile layout.
- Feature commit 57008b4 passed full Windows/Python 3.14 and Chromium checks in GitHub run 40159901327. MSI installation/restart and live route validation passed. The live OCR attempt identified an earlier installation with all three models cached inside RapidOCR but no installer model-folder setting; readiness now recognizes that complete cache too, with a regression check. Compatibility commit 53b7b71 also passed both full Windows/Python 3.14 and Chromium jobs in GitHub run 40160341503. Eleven focused troubleshooting checks pass, including legacy-cache readiness. Release version fields and root VERSION remain unchanged; follow docs/RELEASING.md before publishing.

### Installed-app verification

- Installed on MSI and restarted BEYOND only, leaving other applications running. The dedicated action route and reader validation passed.
- A synthetic screenshot containing “TEST APP: Connection refused”, “Cannot connect to 127.0.0.1:9999” and “Please check the service address.” passed real OCR and text-model advice generation. The answer preserved all three lines, suggested checking the address/port/service, and asked relevant follow-up questions. Saved evidence/advice were present in the recent conversation context.
- The temporary test chat was removed. No existing user chat was read or modified. A copy of the synthetic screenshot was shared with Jeremy for manual testing.
- A test-browser launch on the memory-constrained MSI could not complete; browser validation was completed in GitHub instead. The final live OCR/model check completed successfully with the existing cached models, without installing or downloading another model.
