# BEYOND 1.0.0


BEYOND is a Windows personal AI assistant with a browser interface and tray icon. It supports local text chat,
saved conversations, memories, everyday tools, games and optional voice, photo and image features.
Built-in AI runs on the CPU; external OpenAI-compatible servers can also be configured.
Web lookups and downloads use the network, and an external AI server receives the prompts sent to it.

## Install

Download and fully extract the release source ZIP, then double-click Setup.cmd. It finds compatible Python
3.14 x64 or offers its installation, creates a separate environment and prepares text chat with a small model.
The welcome guide reuses those choices and tests a greeting before opening chat. Add-Features.cmd installs
only the optional features you select, with model notices and compatibility tests.

See [User guide](USER_GUIDE.md), [recovery instructions](../planning/setup-recovery.md) and
[third-party notices](../THIRD_PARTY_NOTICES.md).

## Verified installation path

On a separate Windows PC, Jeremy tested ZIP extraction, existing Python 3.14.5 x64 reuse, environment/library
creation, Qwen3 0.6B download, CPU compatibility, shortcut/tray launch, welcome, normal chat, persistence
and installer rerun. An occupied-port shortcut issue was fixed and retested, including successful recovery.
Whisper tiny microphone input, Kokoro playback, OCR, vision and image generation were confirmed by user testing.
These are functional checks, not an exhaustive hardware-compatibility or model-quality certification.

## Known installation limitation

Automatic Python download/installation on a machine with no Python has not been tested end to end.
If it fails, manually install official Python 3.14 (64-bit) from https://www.python.org/downloads/windows/,
then run Setup.cmd again. Setup.cmd invokes the same bootstrap; switching to that launcher alone does not
bypass a bootstrap problem. The successful test started with Python already installed.

GPU acceleration is not enabled by these installers. Piper on the separate test PC and measured installed
disk use are not confirmed. Optional model terms vary; the selected Piper voice card identifies noncommercial
dataset terms, while Gemma and DreamShaper have separate model-specific conditions.

## Artifact contents

Intended artifact: source code, setup scripts, requirements, documentation and collected notices.
No private data, settings, conversations, .venv, model weights or native engine executables are bundled.
Required runtime components download during setup. Preserve data/files/models when updating an existing copy.
