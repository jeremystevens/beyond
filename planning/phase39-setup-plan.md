# Phase 39: Setup script implementation plan

**Date:** 2026-10-21
**Status:** 39B/39C implemented and verified. 39D optional setup preview implemented; voice and OCR integration verified, full pinned vision/image inference pending. Clean-PC validation remains Phase 42.
**Project:** D:\AI\beyond
**Related roadmap:** planning/phases.md, Phase 39
**Goal:** A new user downloads BEYOND, double-clicks Setup, and reaches verified text chat without manually installing Python, libraries, an engine, or a model.

## 1. Agreed scope

- Initial setup installs text chat only.
- A separate, rerunnable Add Features installer offers voice, vision, and image generation later.
- Detect hardware, recommend appropriate choices, and test compatibility before saving working settings.
- Require Python 3.14; preserve other Python installations.
- Reuse the README's BEYOND block-character banner and tagline: Built Entirely on Your Own Network & Device.
- Provide a plain-text banner fallback and readable progress/error messages.
- Keep all project changes inside BEYOND. Do not change PromptetheusBot or Local AI Studio.
- On Jeremy's MSI, all AI tests remain CPU-only; do not probe its known-unstable NVIDIA acceleration.

## 2. Setup entry points

| Entry point | Intended user | Responsibility |
|---|---|---|
| Setup.cmd | Beginner; double-click | Launch the PowerShell bootstrap from the correct project folder and keep failures visible. |
| setup.ps1 | User without a suitable Python | Find Python 3.14 or offer its verified download and installation, then invoke shared Python setup. |
| setup.py | User with Python already installed | Check the running interpreter; find or offer installation of 3.14 if necessary, then relaunch using it. |
| Add-Features.cmd | Returning user; double-click | Launch the shared optional-feature installer using BEYOND's environment. |

Names for the supporting optional-feature Python/PowerShell files are provisional.
Keep installation logic in shared Python modules; bootstrap scripts should stay small.
The Python entry point must perform its version check before importing third-party dependencies.
Use syntax compatible with the explicitly supported bootstrap Python versions; report unsupported versions clearly.
Do not rely on an unqualified python or pip command selecting the right installation.

## 3. Beginner installation experience

1. Show BEYOND branding and explain that this installs local text chat.
2. Check platform, project folder permissions, Python, hardware, free disk space, and existing installation.
3. Present a recommended configuration, model size, download requirements, and choices to continue or cancel.
4. Offer Python 3.14 installation if missing; prefer per-user installation without administrator access.
5. Create or validate BEYOND's isolated Python 3.14 environment.
6. Install the required text-chat dependencies and a verified compatible llama.cpp build.
7. Reuse a suitable existing model or offer the recommended starter model.
8. Verify downloads, start the engine, and generate a short reply.
9. Save only the successful configuration, show the outcome, and offer to open BEYOND.
10. Offer an optional desktop shortcut and explain how to add features later.

Paths with spaces and non-ASCII characters must work. Resolve paths from the script location, not the caller's current directory.
Do not silently change machine-wide PowerShell policy, PATH, firewall rules, or existing Python installations.
Check the actual Python 3.14 environment before installing any dependencies.
A missing Internet connection should produce a useful message and allow reuse of complete local assets.

## 4. Hardware profile and recommendations

Refresh the profile whenever either installer runs. Record:
- Windows version and architecture.
- CPU architecture, logical cores, and relevant instruction support.
- Total and currently available RAM.
- GPU vendor/model, dedicated video memory where reliably detectable, and available runtime support.
- Free disk space on the actual destination drive.
- Selected settings, compatibility outcomes, and useful failure details.

Keep hardware/settings records local and exclude machine-specific records from git.
Total RAM informs the recommendation; available memory and context size affect whether a model can load now.
Model file size is not the same as total runtime memory. Allow for the engine, context cache, BEYOND, and Windows.
Start with conservative CPU settings and a modest context; offer acceleration only after a successful test.
Never decide compatibility from the GPU name alone.
Use plain descriptions such as Recommended, Faster with lower quality, and Better quality but slower.
Advanced overrides remain available; save the tested result instead of assuming an override will work.

## 5. Starter models

| Role | Model | Download size | Evidence |
|---|---|---|---|
| Default starter | Qwen3-1.7B-Q8_0.gguf | 1.71 GiB as displayed in BEYOND | Jeremy downloaded and tested it on CPU through the Models feature. |
| Smaller fallback | Qwen3-0.6B-Q8_0.gguf | Approximately 639 MB on Hugging Face | Jeremy downloaded it and confirmed it works. |

Fallback source: https://huggingface.co/Qwen/Qwen3-0.6B-GGUF
Inspect the current Models page implementation before choosing download URLs or adding parallel download code.
Reuse its trusted sources, model metadata, integrity checks, and compatible model selection where suitable.
Pin exact filenames, revisions, byte sizes, and SHA-256 hashes during implementation.
Treat the smaller model as a basic-chat/testing option with reduced answer quality.
Offer it when memory is insufficient or the default model fails for a resource-related reason.
Do not download another model to address unrelated problems such as a blocked port or corrupt engine.
If a lighter configuration is needed, explain the reason and additional download before proceeding.
Allow users to select an existing compatible model and avoid downloading duplicates.

## 6. Compatibility checks

| Component | Test | Success condition |
|---|---|---|
| Python | Run the selected interpreter and environment | Python 3.14, correct architecture, and isolated environment confirmed. |
| Libraries | Install then import required runtime modules | Required text-chat components import successfully. |
| Engine | Launch the selected llama.cpp binary | Engine starts and responds locally without disturbing other services. |
| Text model | Load and request a short non-thinking reply | A non-empty usable completion returns within a generous, visible test window. |
| GPU, when appropriate | Small inference using proposed acceleration | Inference succeeds; otherwise offer tested CPU fallback. |
| Whisper, optional | Transcribe a bundled licensed audio sample | Expected words are recognized with reasonable normalization. |
| Kokoro, optional | Synthesize a short sentence | A valid, non-empty playable audio file is produced. |
| Vision, optional | Ask about a bundled licensed test image | A relevant response returns using the required model/projector combination. |
| Image generation, optional | Generate a small image | A valid image is produced using the selected backend and model. |

Separate startup, model loading, and generation progress so slow hardware is not reported as an immediate failure.
Use bounded, configurable timeouts; offer retry/wait guidance for slow systems.
Distinguish technical smoke-test success from broad answer quality.
Use lower context or lighter settings for memory-related failures before declaring incompatibility.
Shut down only processes started by the installer, including after cancellation or failure.
No setup tests should call external AI services.

## 7. Optional Add Features installer

Show each feature independently with installed status, download size, disk requirements, and expected hardware suitability:
- Voice input: Whisper and its required runtime/model files.
- Spoken replies: Kokoro and its required runtime, model, and voice files.
- Vision: the assets and engine support used by /look.
- Image generation: the assets and engine support used by /imagine.

Allow voice input and spoken replies to be selected separately or together.
Audit existing integrations to identify the exact packages, executables, models, and licenses.
Install only selected components. Reuse BEYOND's Python environment and shared download/hardware helpers.
Rerunning should recognize verified installed components and skip unnecessary work.
Test each selected feature before marking it ready; unrelated working features remain usable after a failure.
Provide a useful summary: ready, skipped, or needs attention, with clear next steps.

## 8. Download integrity, retries, and recovery

- Use official Python and llama.cpp sources and trusted Hugging Face repositories.
- Maintain a versioned asset manifest with pinned versions/revisions, licenses, sizes, and checksums.
- Download into temporary partial files; verify before promoting to final filenames.
- Resume only when the server and remote asset identity support safe continuation.
- Check space for downloads, extraction, and installed files before starting.
- Use clear progress, bounded network timeouts, retries, and actionable errors.
- Make reruns safe; detect incomplete installations and continue or repair explicitly.
- Never overwrite a user's model, settings, or environment silently.
- Log steps and failure details without secrets, conversation contents, or unnecessary personal data.
- Retain useful validated downloads after failure; avoid deleting unrelated files.

## 9. Existing installations and app integration

Inspect current configuration, engine management, model downloads, requirements, launch behavior, and documentation first.
Preserve chats, memory, settings, custom models, and existing server connections.
Validate an existing environment before reuse; offer repair/recreation if its Python version is wrong.
Separate optional dependencies from the base install so text-only setup is actually lightweight.
Follow existing configuration helpers and port definitions instead of introducing duplicate defaults.
Fresh installs use BEYOND's built-in engine on an automatically selected free port.
The web app uses its existing default port 7770; report conflicts clearly.
Existing external-engine settings must not be silently replaced.
Coordinate with Phase 40: installation/configuration choices are reused by the welcome screen.
Phase 40 handles introduction and personalization without repeating completed downloads or setup questions.

## 10. Implementation sequence

### 39A: Audit and asset manifest
- Read project rules and current dependency/configuration/engine/model code.
- Confirm Windows 10/11 x64 support and Python bootstrap compatibility.
- Identify text-only requirements and optional dependency groups.
- Pin Python, llama.cpp, starter models, integrity metadata, and licenses.
- Done when: implementation choices and exact assets are documented.

### 39B: Shared preflight and Python bootstrap
- Add branding, project path handling, Python discovery/install offer, and environment validation.
- Add Setup.cmd, setup.ps1, and setup.py entry points.
- Done when: each entry path reaches the same setup under Python 3.14.

### 39C: Verified text-chat installation
- Add resumable downloads, base dependencies, engine setup, model reuse/selection, and hardware recommendations.
- Run CPU chat verification; persist successful settings and provide launch/shortcut options.
- Done when: a fresh folder reaches working text chat.

### 39D: Optional features
- Add the separate feature installer with individual choices, shared helpers, and feature tests.
- Done when: selected extras work and text chat remains usable if an optional install fails.

### 39E: Recovery, documentation, and acceptance
- Verify reruns, cancellation, failures, existing installs, and paths with spaces.
- Update README, CHANGELOG, and the Phase 39 roadmap status.
- Follow project commit rules at completed milestones; Jeremy Stevens identity, no AI co-author trailer.
- Done when: the acceptance checks below pass and limitations are documented.

## 11. Acceptance checks

- No Python installed: beginner launcher offers installation and reaches Python 3.14 setup.
- Only another Python installed: preserve it and offer/find 3.14.
- Multiple versions installed: explicitly select 3.14.
- Existing healthy or wrong-version environment: reuse safely or offer repair.
- Fresh text-only install: no voice, vision, or image-generation downloads.
- Existing starter/fallback/custom model: reuse without duplicate downloads.
- Low available memory: explain and test a smaller configuration/model.
- Interrupted/corrupt download: resume safely or redownload after verification failure.
- Offline, insufficient disk, unwritable path, and occupied web port: clear next steps.
- Existing settings and data: preserved.
- Slow CPU, rejected acceleration, cancellation, and installer failure: clean process handling.
- Optional installer rerun: installed assets detected and only selected missing components installed.
- Working text chat remains available after an optional feature failure.
- Windows paths with spaces/non-ASCII characters and launch from another directory work.
- Final clean-machine validation remains Phase 42; local success alone does not prove a fresh-PC install.

## 12. Items to resolve during the audit

- Exact supported Python bootstrap versions and Python 3.14 patch release.
- Pinned llama.cpp builds and CPU instruction-set compatibility.
- Default model's existing trusted repository, revision, byte size, and checksum.
- Base versus optional dependency boundaries, including Python 3.14 wheel availability.
- Hardware recommendation thresholds, context sizes, and timeout defaults based on measurements.
- Optional-feature model choices and their required companion files.
- Installer state/log locations using the project's existing conventions.

This document authorizes planning only. No installer implementation, dependency installation, model download, commit, or push is performed by saving it.
