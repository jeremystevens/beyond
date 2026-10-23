# Phase 42: clean-install acceptance

Started 2026-10-22. Status: user-guided installation on a separate PC is in progress. Results below distinguish confirmed checks from pending cases.

Only the existing MSI development PC was connected when this checklist was prepared. Do not remove Python, change its working installation, close essential apps or occupy its live BEYOND port to simulate a fresh PC. Jeremy chose to run the remaining installation and large-model checks on a fresh machine.

## Record before installing

- Test PC / Windows version / x64 architecture:
- Installed and available RAM / CPU:
- Free disk before setup (10 GB is an initial text-only allowance, not an extras requirement):
- Python already present? A no-Python environment is needed for the bootstrap acceptance case:
- Source commit / ZIP downloaded directly from GitHub:
- Fresh writable project folder; no copied data, settings, .venv or external Studio/bot dependency:

## Run in order

1. Download/extract the current main-branch ZIP and follow docs/USER_GUIDE.md without development shortcuts.
2. Double-click Setup.cmd. With Python absent, verify the offer, signed/pinned Python installation, version selection and isolated environment creation. Preserve any other Python installation in separate version-selection tests.
3. Choose one small CPU model. Verify downloads, compatibility reply, saved configuration and optional shortcut. Record time, downloaded bytes and disk usage after setup.
4. Open BEYOND, complete Welcome using Keep current and Test my AI, then send a normal chat message. Confirm default port, local-only access, saved conversation after restart and no requirement for Local AI Studio.
5. Rerun Setup and confirm verified reuse and preserved data/settings. Check clear recovery for interrupted downloads or insufficient resources when practical; record actual outcomes rather than assuming earlier fixture tests cover the fresh PC.
6. Quit the test copy of BEYOND normally. On this fresh test environment only, use an owned temporary listener on the default web port and verify startup gives the expected conflict message. Close only that test listener and verify normal launch again.
7. Add optional features individually when the fresh machine has adequate memory/disk. Verify text chat after each. Test the pinned vision model/projector against the generated image and DreamShaper against a real output image. These two inference checks remain required and unverified.
8. Verify Add-Features rerun/retest, failure/skip behavior and persistence. Record each selected feature as passed, failed or not tested.

## Result log

Keep local logs private. Report redacted error text and the failed step for fixes. Record exact source revision for each retry. Preserve the failed environment for diagnosis before replacing anything.

Overall result: tested paths accepted by Jeremy; proceed with release preparation with the explicit exceptions below.
No-Python bootstrap: pending; test PC already had Python 3.14.5 x64.
Text install / welcome / normal chat: passed by Jeremy's report.
Port conflict: passed after the two-file fix; native dialog screenshot supplied, followed by successful normal startup and chat.
Optional voice/OCR on separate test PC: Whisper tiny, Kokoro and OCR passed by Jeremy report.
Vision installation and photo test: passed by Jeremy report on the separate PC; exact log/source revision not independently collected.
Image installation and generation: passed by Jeremy report on the separate PC; exact log/source revision not independently collected.
Measured disk use: pending.

Do not mark Phase 42 complete or prepare a final release until actual acceptance outcomes are recorded and required failures are resolved.

## User-guided results, 2026-10-22

Separate test PC, extracted GitHub ZIP at E:/beyond-main, 11.7 GiB installed RAM. Python 3.14.5 x64 was found
and reused. New environment creation, text libraries and app startup passed. Low-memory Retry was exercised
while a VirtualBox snapshot completed; setup later continued with more memory available.
Qwen3 0.6B Q8_0 downloaded and passed CPU chat compatibility. The installer created the shortcut, launched the
tray and opened Welcome. Its greeting test passed. A normal rainbow explanation returned successfully
(78 tokens, display showed 4 seconds / 27.35 tokens per second).
Jeremy quit and reopened through the shortcut; Welcome did not repeat and the saved conversation remained.
A Setup rerun verified the environment, reused the existing model, passed its chat test and preserved the chat.

The temporary loopback HTTP server on the default port remained running during the conflict test.
Desktop startup showed a tray icon but no useful error. Console startup correctly identified python.exe and
its PID, but included obsolete Phase 4 instructions. After Ctrl+C stopped only the temporary listener,
normal startup and a chat reply worked. These findings motivated the two-file fix in beyond.py/app/ports.py.

The no-Python installer case, optional-feature checks (including pinned vision/image inference), exact source
revision of the original ZIP, and measured installed folder size remain unverified. Free disk readings on
a busy PC are not a measured installation size. Do not mark the whole phase complete.

## Startup fix

Shortcut/tray port failures now show a native Windows error dialog as well as the existing logged message.
Console launches print the error without opening a dialog. The server begins through pystray's ready/setup
callback, avoiding icon.stop before icon.run has initialized. Guidance names the saved settings file and
web_port field; it no longer tells users to change code defaults or wait for a future Settings page.
The fresh test ZIP must receive these changed files before Jeremy repeats the shortcut-conflict check.

Verification of startup fix: 43 targeted checks passed across startup errors, authentication and Welcome.
Eight new launcher checks cover native-dialog invocation (mocked to avoid opening a dialog on the working PC),
console-only output, dialog failure fallback, real occupied-port refusal without touching the listener,
program naming, duplicate-instance guidance, a free port, and tray readiness before stop. The first test
fixture encountered Windows SQLite cleanup locks; launcher tests were isolated from database initialization.
No live app was restarted, no other app was stopped, and no model was loaded for these regression tests.
Actual native dialog visibility on Jeremy's fresh test PC still requires the updated-shortcut test.

## Acceptance update and release-preparation decision

Jeremy replaced beyond.py and app/ports.py in the test ZIP, repeated the occupied-port shortcut launch,
and supplied a screenshot of the native error dialog with corrected instructions. After stopping the test
listener, normal launch and a chat reply passed again.

Whisper tiny: installer reported Ready, with checksums and offline CPU test completed. Microphone transcription
of the France question and the subsequent chat reply passed; Jeremy reported quick response.
Kokoro: installer reported Ready and Jeremy confirmed actual spoken-reply playback.
OCR: Jeremy confirmed installation and reading-text testing worked.
Vision: Jeremy confirmed downloading, installation and manual photo testing worked.
Image generation: Jeremy confirmed downloading, installation and actual image generation worked.
These last three results are user reports; no raw worker logs or exact model/source revision were collected
through this chat. Optional rerun skipping was verified earlier in a disposable development integration,
not yet demonstrated by a fresh-PC transcript. Piper on the separate PC is not confirmed.

The PC already had Python 3.14.5. No machine without Python is available, and Jeremy chose to defer that
case rather than uninstall Python or build a VM. Proceed with Phase 43 preparation with that limitation
explicitly disclosed; it is not a successful no-Python test. Setup.cmd uses the same bootstrap and is not
an independent workaround. Fallback: manually install official Python 3.14 x64, then rerun Setup.cmd.
This reuses the existing-compatible-Python path demonstrated on the test PC; the manual installation step
itself was not part of that test. Installed folder size also remains unmeasured.
