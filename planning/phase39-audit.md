# Phase 39A: Setup implementation audit

Date: 2026-10-21
Repository: D:\AI\beyond
Status: Source audit and initial asset selection complete; dependency resolution and optional-asset verification remain open.
No installer code or installed dependencies were changed. No models were downloaded.
Initial git status: only planning/phase39-setup-plan.md was untracked.

## Verified baseline

- App version: 0.38.4; roadmap phase: 38.
- Existing environment: Python 3.14.8.
- Configured llama-server reports version 9668, commit 32120c10e, Clang 20.1.8, Windows x86_64.
- Existing runtime/model/settings folders are already git-ignored.
- No AGENTS.md found at D:\, D:\AI, the project root, or planning in the locations checked.
- Follow planning/phases.md: work only in BEYOND, preserve other apps, CPU-only on Jeremy's PC, Jeremy's git identity without AI co-author credits.

## Source findings and implementation decisions

### Dependency separation is required
requirements.txt and requirements-lock.txt currently combine base app, OCR, Whisper, Kokoro, and Piper.
Installing either unchanged would violate the approved text-only experience.
Proposed base direct dependencies: fastapi, uvicorn, psutil, httpx, requests, tzdata, ddgs, segno, dateparser, pystray, pillow, Windows-Toasts, cryptography.
Confirm the complete import graph and resolve/test this group in an isolated temporary environment before calling it a supported lock.
Keep the existing full lock intact until replacement groups are verified.
Optional groups:
- OCR: rapidocr, onnxruntime, opencv-python-headless and resolved dependencies.
- Voice input: faster-whisper and resolved dependencies.
- Kokoro: kokoro-onnx and resolved dependencies.
- Piper fallback: piper-tts and resolved dependencies; offer separately instead of silently installing.
- Vision/image generation: Pillow is already used by the base tray; download the native engines and matching model assets separately.

### OCR currently blocks a minimal installation
app/server.py imports app.tools.scan; commands and photo jobs also reference scan.
scan.py imports onnxruntime unconditionally at module scope before Windows toast imports.
This ordering fixes a documented native DLL crash. A simple lazy import after toast initialization could reintroduce it.
Required design: attempt the early ONNX preload only when installed, retain the safe initialization order, and give an actionable unavailable-feature response without preventing text chat.
Add OCR to Add Features as a separate choice; photo validation must remain available without OCR.

### Whisper must be explicitly provisioned
app/tools/speech_to_text.py hardcodes MODEL='base'.
_model() uses WhisperModel(MODEL, device='cpu', compute_type='int8'), allowing a first-use Hugging Face download.
Add a configured local model path, explicit installer download, and local-only loading.
Expose tiny/base hardware choices only after companion files and compatibility are verified.
Audit the runtime warm-up path so text-only startup never downloads or loads Whisper.
Kokoro/Piper native imports are isolated in speech_worker.py; retain subprocess isolation.

### Engine and acceleration
app/builtin_engine.py already supplies process management, free-port selection, health checking, and a 300-second startup timeout.
It forces --n-gpu-layers 0 and CUDA_VISIBLE_DEVICES=-1.
Vision forces CPU and disables projector offload.
Image generation accepts only sd-cli.exe inside a folder named cpu.
Therefore recording GPU hardware is straightforward, but enabling acceleration needs explicit settings/validation/runtime changes across relevant engines.
Do not claim GPU presets work merely because the installer detects a card.
Deliver the verified CPU path first; retain acceleration as unfinished until implemented and tested on suitable hardware.
Never test NVIDIA acceleration on Jeremy's MSI.

### Reuse existing model logic carefully
app/downloads.py already has SHA-256 verification, .part files, retries, Range resume, disk checks, license handling, and model-folder destinations.
The 1.7B starter is already in RECOMMENDED with a pinned size/hash; the 0.6B fallback is not.
Current URLs use main rather than immutable revisions.
Extract/reuse shared download primitives where possible; do not start the application's background downloader just to bootstrap.
Preserve app downloads.json and avoid racing the running app's downloads.
Use immutable revisions for installer assets.
app/models.py discovers nested model files and preserves per-model profiles.
Reuse app/settings.py validation and merging after dependencies are installed; never write a complete replacement settings file.

## Verified initial assets

Metadata fetched directly from official Hugging Face/GitHub services on 2026-10-21.

### Default model
Repository: Qwen/Qwen3-1.7B-GGUF
Revision: 90862c4b9d2787eaed51d12237eafdfe7c5f6077
Filename: Qwen3-1.7B-Q8_0.gguf
Bytes: 1834426016
SHA-256: 061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a
License: Apache 2.0, also recorded in the current app catalogue.
URL: https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf

### Smaller fallback
Repository: Qwen/Qwen3-0.6B-GGUF
Revision: 23749fefcc72300e3a2ad315e1317431b06b590a
Filename: Qwen3-0.6B-Q8_0.gguf
Bytes: 639446688 (about 610 MiB; Hugging Face displays 639 MB)
SHA-256: 9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031
License: Apache 2.0 on the official repository; include its notice.
URL: https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/23749fefcc72300e3a2ad315e1317431b06b590a/Qwen3-0.6B-Q8_0.gguf

### CPU engine candidate matching the installed version
Release: b9668
Filename: llama-b9668-bin-win-cpu-x64.zip
Bytes: 16910863
Published GitHub asset SHA-256: 47e365fcaa33c875330479411d372f87ce992df791562aecb4f9c1bae869d943
URL: https://github.com/ggml-org/llama.cpp/releases/download/b9668/llama-b9668-bin-win-cpu-x64.zip
Before shipping: verify archive layout, bundled DLLs/licenses, supported CPU instruction sets, and all CLI flags used by BEYOND.
Installed version output alone does not establish that this archive supports every target CPU.

### Python bootstrap candidate
Version: 3.14.8, standard Windows x64 build, matching the existing environment.
URL: https://www.python.org/ftp/python/3.14.8/python-3.14.8-amd64.exe
Official endpoint returned HTTP 200 to a HEAD request.
Still required: independent published integrity/signature verification and installer option validation.
Do not mark a reachable installer as verified.
Proposed setup.py bootstrap floor: Python 3.8, with no newer syntax or third-party imports before relaunch under 3.14.
PowerShell path should work without any Python installed.

## Runtime integration

- Root paths already derive from __file__ in config.py.
- Use data/setup/ for local state, hardware profile, and logs (already excluded from git).
- Proposed native tool location: tools/llama.cpp/b9668/cpu/; add generated tools/download caches to gitignore during implementation.
- Preserve model directory conventions: models/<owner>--<repo>/.
- Use existing config.WEB_PORT, RESERVED_PORTS, and builtin_engine.free_port instead of repeating port values.
- Fresh installs remain local-only with the built-in engine.
- Keep CPU threads within available cores and start with a modest context; exact thresholds need measurement.
- A test should use an installer-owned subprocess with isolated settings and free port, avoiding the running app's global engine/PID handling.
- Do not import app.server for a basic dependency check: it initializes application stores at import time.
- Use short non-thinking completions and distinguish slow startup from inference failure.

## Remaining 39A checks before marking the stage done

1. Resolve and verify a Python 3.14 Windows x64 text-only lock, including binary wheel availability.
2. Verify the Python installer's provenance/integrity and bootstrap install/relaunch behavior.
3. Inspect/test the pinned CPU archive without replacing the current engine.
4. Pin Whisper, Kokoro, optional Piper, vision model/projector, image engine/model, and licensed test samples.
5. Confirm optional capability/UI handling so text-only users receive clear Add Features guidance.
6. Set measured RAM/context/timeout thresholds; do not infer hard minimums solely from file sizes.
7. Document acceleration support limits honestly until runtime support is added and tested.

Next implementation stage: 39B bootstrap after these prerequisites are resolved.
No phase-completion commit yet: 39A is not fully complete.

## Follow-up dependency check

The proposed 14-package base group was checked with the existing Python 3.14.8 environment using:
pip install --dry-run --ignore-installed --only-binary=:all: with the direct versions from requirements-lock.txt.
Result: exit code 0. The resolver found a compatible binary-only dependency set without installing it.
This checks package resolution/wheel availability for this machine; it is not a clean-environment import or app-startup test.
A complete transitive lock and isolated text-only smoke test remain required.
The app lifespan was also inspected: it does not call speech_to_text.warm_up at startup.

## Isolated environment test attempt

A separate Python 3.14 environment was created at D:\temp\beyond-39a-w58_97sf.
The binary-only base dependency installation failed in pip while reading package metadata with MemoryError (exit code 2).
A follow-up memory check reported 17,018,621,952 bytes total and 629,829,632 bytes available (about 601 MiB).
The import and pip-check stages were not reached. This is not a successful clean-environment validation.
The working project .venv was not modified. No user applications were stopped.
Retain the temporary audit environment for inspection/retry after memory pressure is relieved.
The nested import-test command also needs corrected Windows quoting before retrying; use a script file or avoid nested quoted Python strings.
Installer preflight should handle low currently available memory separately from total installed RAM, with a retry option and an explanation.

## Isolated dependency retry: passed

After memory became available, the same 14 pinned base dependencies installed successfully in D:\temp\beyond-39a-w58_97sf (pip exit code 0).
Available RAM before retry: 2,244,263,936 bytes (about 2.09 GiB).
All 14 corresponding modules imported successfully in a fresh subprocess.
pip check reported: No broken requirements found (exit code 0).
The project's working .venv remained untouched.
This supersedes the failed installation attempt for the base-package compatibility check.
It does not yet validate full text-only app startup: the mandatory scan.py ONNX import still requires the planned optional-dependency changes.

## Phase 39B implementation

The owner accepted 39A and authorized 39B. Remaining optional-asset checks move to the relevant integration stages.
Added Setup.cmd, setup.ps1 and setup.py (standard-library bootstrap, Python 3.8+ entry syntax).
Read-only mode validates discovery/environment without installing. Normal mode offers Python 3.14.8 per-user installation
and environment creation; invalid existing environments are preserved, with explicit instructions.
The existing .venv, settings, models, running applications and unrelated test edits were left alone.

Python 3.14.8 installer downloaded from the official URL above, without executing it.
Windows Authenticode: Valid; publisher CN/O Python Software Foundation.
Verified-file SHA-256: 759be887b96e736a3ca886daf8d575f18fcae1a09efab6902f42d59e8999f8ef
Both this pinned hash and a valid publisher signature are now required before execution.
The verified download is cached under data/setup/downloads, excluded from git.

Validation:
- 11 Python bootstrap tests passed, including real temporary venv creation/reuse under a path with spaces,
  invalid-environment preservation, cancellation, wrong version/architecture rejection, interpreter relaunch,
  and read-only behavior when Python is missing.
- PowerShell parser and five signature cases plus checksum rejection passed.
- Python and PowerShell direct read-only entry points passed.
- Setup.cmd --check passed when launched from a different working directory.
- No Python installer was run: per-user installation on a machine lacking Python remains a clean-PC test.
- Full app installation/startup is intentionally deferred to 39C; optional features to 39D.
