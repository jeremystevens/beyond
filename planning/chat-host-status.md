# Host status and model awareness

Status: implemented after 1.2.0; unreleased
Date: 2026-10-25

## Delivered
- /status reports BEYOND host CPU, RAM, installation-drive usage/free space, system uptime, optional NVIDIA metrics and AI/model state.
- /model and narrowly matched whole-message identity questions return runtime information without inference or memory lookup.
- Built-in ready versus loading/unavailable states are distinguished. External server selection is not proof of a physical model loaded in every server implementation.
- Normal chat receives built-in model state or a recent server stream observation (60 seconds). Settings changes invalidate observations. Prompt context alone cannot guarantee a correct LLM answer.
- GPU queries use an existing nvidia-smi executable, bounded to two seconds with graceful failure. No added dependency or GPU inference.
- Command registration automatically includes both commands in /help and autocomplete. Reports persist as ordinary command snapshots.

## Validation
- Six focused status/model tests pass on MSI, Windows/Python 3.14; four existing prompt tests pass.
- Full Windows/Python 3.14 and Chromium checks passed on feature commit c2862273d5f59383305a45e92e7021f7a9f3e0a1 (Actions run 40218280149).
- Live /status returned host resources and the ready Gemma model.
- Exact question “What model are you running” was tested through the public application address and returned the active GGUF filename directly. Only the test-created chats were removed.
- User confirmed current-model lookup works.
- Documentation-only follow-up receives its own CI checks before merge.

## Release boundary
No new release is being published by this merge. Root VERSION and app/config.py release version/phase remain unchanged. Follow docs/RELEASING.md when a release is selected.
