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

## Phase 39C: text-only setup implemented

Added installer/text_setup.py, installer/assets.json, requirements-text-lock.txt and installer recovery tests.
Setup.cmd/setup.ps1/setup.py now continue into the shared text installer. --check remains read-only and reports hardware.
Only CPU execution is supported by this stage; NVIDIA acceleration was never attempted on the owner's MSI.

Behavior:
- Exact text-only dependency pins exclude ONNX/OCR, Whisper, Kokoro, Piper and image engines.
- Installed RAM informs starter/fallback recommendations; currently available RAM is rechecked at expensive steps.
- Temporary shortages offer Retry, explicit Try anyway, and an optional smaller-model choice without misclassifying hardware.
- Existing matching models are hash-verified and reused. User-selected local GGUFs are tested without modification.
- Hugging Face model revisions and CPU engine archive are pinned by size/SHA-256.
- Range resume is validated; ignored Range safely restarts; complete corrupt partials cannot loop forever on Retry.
- Extraction rejects traversal/links and verifies existing engine files against the pinned archive.
- An install lock prevents simultaneous installers; a running app/occupied configured port must be resolved before library changes.
- Startup verification runs the real app against disposable stores. Inference runs an installer-owned engine on a free loopback port.
- Engine failures only offer a smaller model/lower context when memory-related; other failures retain the actual diagnosis.
- Only successful settings are merged, existing settings are backed up, and changes made during setup are not overwritten.
- Existing external connections require agreement before activation of the tested built-in model.
- Shortcut creation and launching are optional; existing shortcuts are not overwritten.
- Hardware, step logs and successful results are kept locally under data/setup.
- app/tools/scan.py permits missing ONNX while retaining early native preloading when installed.
- Optional OCR/voice endpoints now explain that text chat remains available.

Verification:
- 24 bootstrap/installer unit tests passed.
- Existing scan (8), voice-input (7) and built-in-engine (11) tests passed: 50 tests in total.
  Existing SQLite ResourceWarnings in engine tests did not fail assertions.
- The pinned text lock installed successfully in the separate Python 3.14 audit environment; working .venv was untouched.
- That environment has no onnxruntime, faster_whisper or kokoro_onnx; real app startup/page request passed.
- Installer app-health verification also passed in that environment with disposable data.
- Full installer integration ran in D:\temp\beyond 39c integration e97odppr, with a junction to the audit environment
  and read-only reuse of the existing model folder. Its settings used a separate free web port.
- The integration downloaded/verified/extracted llama.cpp b9668, reused the verified Qwen3 0.6B file, generated
  "Hello! How can I assist you today?", stopped its own engine and saved tested settings only in the disposable copy.
- Launch and shortcut were intentionally skipped in the integration; both running bots and owner settings were preserved.
- On this busy PC the integration explicitly chose Try anyway for the known small model after checking >1.25 GiB free.
  Normal installations retain their conservative memory prompts.
- Setup.cmd --check reports Python/environment/hardware without installation or settings changes.

Remaining:
- 39D: separate optional-feature installer.
- 39E: additional recovery/user-experience hardening.
- Phase 42: fresh-PC/no-Python validation; the disposable integration is not claimed as a clean-machine test.
- GPU acceleration remains unimplemented; detection alone is not a compatibility guarantee.

## Phase 39D preview: optional features

39C is on origin/main (confirmed while the remote also included the later test-fix commit).
Added Add-Features.cmd and the shared Python optional installer, pinned optional asset manifest, per-feature
requirements/constraints, offline feature worker, Windows job process guard and recovery tests.
The preview supports independent Whisper tiny/base, Kokoro, Piper, OCR, Gemma vision and DreamShaper choices.

Implementation:
- Optional package constraints preserve the text-only runtime pins; unselected packages are not installed.
- Model download sizes, estimated free RAM and licenses are presented before each feature.
- Each selected feature is prepared, tested and saved independently. Retry, Skip and cancel-remaining are distinct.
- Ready records include selected configuration, package versions and file size/mtime fingerprints.
  Changed/missing files, package changes or changed settings require verification again.
- Model/native downloads retain the shared pinned SHA-256 and safe resume/extraction checks.
- Source model assets are pinned to Hugging Face revisions; Kokoro uses pinned GitHub release downloads.
  RapidOCR model URLs and SHA-256 values come from RapidAI's versioned v3.10.0 publisher manifest.
- Kokoro release assets without publisher digest fields were fetched from the official release and their SHA-256
  values recorded. No user model files were altered.
- Native SD CPU release master-987-a77d362 is pinned by GitHub's published asset digest.
- Workers deny network connections during compatibility tests and use CPU backends explicitly.
- Whisper gets a configured local model folder and local_files_only=True. Legacy cached base remains usable
  offline; recording never starts a new download.
- OCR accepts a configured folder containing its three explicitly downloaded models.
- Piper can be installed alone or as a fallback without replacing an active Kokoro selection.
- Each feature test belongs to its own Windows job; closing the job on timeout/cancel closes its native children.
- Settings are merged only after passing the selected feature test. Original settings are backed up and concurrent
  changes are rejected. Test requests contain only relevant feature settings.

Verification so far:
- Optional dependency groups installed successfully in the separate Python 3.14 audit environment; working .venv untouched.
- Disposable copy D:\temp\beyond 39d integration wf4ccuk9 completed real Whisper tiny, Kokoro, Piper and OCR tests.
- Whisper recognized the generated local speech sample; Kokoro and Piper produced validated WAV files.
- OCR recognized the generated HELLO WORLD 42 sample with networking denied.
- Text-chat app health checks passed after each selected optional library installation.
- Rerunning verified selections skipped all four without downloading/testing again.
- The isolated copy retained Kokoro as primary when Piper was added; original owner settings were not changed.
- Native child-process cleanup was tested with an owned parent/child pair; both stopped when their job closed.
- Latest dedicated optional tests: 11 passed, including malformed state, failure isolation, offline Whisper and type checks.
- Pinned CPU SD executable extraction and all command flags used by the app passed interface checks.
- Pinned llama-mtmd-cli extraction and required vision command flags passed interface checks.
- Add-Features.cmd --check passed without installing or activating features.

Remaining before calling all of 39D validated:
- Run real Gemma/projector and DreamShaper inference tests with the pinned engines when enough RAM is available.
  This busy PC currently has roughly 1.5-2.3 GiB free; no large-model test was forced and neither running bot was stopped.
- Clean-machine installation remains Phase 42. The disposable-copy integration is not a fresh-PC claim.
- GPU acceleration remains unsupported by this installer.

Final regression result for this milestone: full suite passed, 289 tests in 579 seconds.
The latest dedicated optional tests also passed (11 checks), including the added malformed-state guard.
Existing SQLite ResourceWarnings/debug timing output did not fail the suite.
39D remains a preview until the two large-model inference checks above have run.

## Owner decision: defer large-model validation to a fresh machine

On 2026-10-21, Jeremy approved leaving Local AI Studio, PromptetheusBot, BEYOND,
and connected ChatGPT/Claude work sessions running on the development PC.
Do not close these applications or force large-model tests to reclaim RAM.
Run the remaining pinned Gemma/projector vision and DreamShaper image-generation
inference checks on the owner's fresh-machine installation as part of Phase 42.
39D remains a preview with these checks pending; this deferral is not a passing result.
The installer must still pass each feature's compatibility test before enabling it.
