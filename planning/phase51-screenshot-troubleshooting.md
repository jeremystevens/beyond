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

- Ten isolated Python checks cover OCR/vision selection, missing dependencies, evidence-based generation, saved follow-up context, arrivals, unreadable evidence, validation, failures, deletion, cancellation and busy/empty models.
- Browser checks cover attachment and clipboard preview, action/context/reader submission, result rendering/Copy, literal HTML safety, recovery after missing features, and narrow mobile layout.
- Full CI and installed-app checks will be recorded after execution. Release version fields and root VERSION remain unchanged; follow docs/RELEASING.md before publishing.
