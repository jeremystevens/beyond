# Third-party notices

BEYOND's own source is licensed under the [MIT License](LICENSE), copyright Jeremy Stevens. That license does not replace the licenses of Python, installed packages, native engines, downloaded models, voices or online content. The installers fetch those components separately; the source repository does not include model weights or engine executables.

This index accompanies the pinned setup manifests and the Python dependency snapshot collected on 2026-10-21. Full collected notice texts are in [docs/licenses](docs/licenses/README.md). Keep upstream notices with any components you redistribute. A source-code checkout and a bundled executable/environment are different distribution artifacts; the final binary bundle still needs its own inventory before Phase 43.

## Browser syntax highlighting

Highlight.js 11.11.1 (common language bundle plus PowerShell grammar) is redistributed under BSD-3-Clause. Local assets and the complete upstream license are in [app/web/vendor](app/web/vendor); [the vendor README](app/web/vendor/README.md) records pinned sources and SHA-256 values. No CDN is contacted at runtime. BEYOND's code-block stylesheet is project-owned.

## Engines and Python

| Component | Source / terms | Included material |
|---|---|---|
| Python 3.14.8 | [Python license](https://docs.python.org/3/license.html), PSF and incorporated licenses | Upstream LICENSE snapshot; setup downloads the official signed installer. |
| llama.cpp b9668 | [MIT](https://github.com/ggml-org/llama.cpp/blob/b9668/LICENSE) | Pinned source license snapshot. The downloaded CPU archive can include additional libraries whose notices must also be retained. |
| stable-diffusion.cpp a77d362 | [MIT](https://github.com/leejet/stable-diffusion.cpp) | Source license snapshot; inspect the final archive's incorporated components when preparing a binary distribution. |
| Piper runtime | [GPL-3.0-or-later](https://github.com/OHF-Voice/piper1-gpl) | The installed piper-tts package's notice files. This is distinct from the selected voice's model-card terms. |
| eSpeak NG / phonemizer | [eSpeak NG](https://github.com/espeak-ng/espeak-ng), [phonemizer](https://github.com/bootphon/phonemizer) | GPL-related upstream/package notices are collected. A loader or wrapper's license does not replace the speech engine's license. |
| PyAV / FFmpeg | [PyAV](https://github.com/PyAV-Org/PyAV), [FFmpeg](https://ffmpeg.org/legal.html) | PyAV's package metadata/notices are recorded. FFmpeg licensing depends on the compiled build; inspect the exact wheel's incorporated libraries before redistributing a bundled environment. |

## Downloaded models and voices

The exact file URLs, revisions, byte sizes and SHA-256 values live in [installer/assets.json](installer/assets.json) and [installer/optional-assets.json](installer/optional-assets.json). Model-card snapshots retain the source descriptions; they do not grant new rights.

| Selection | Upstream terms / attribution |
|---|---|
| Qwen3 1.7B and 0.6B GGUF | Qwen / Alibaba Cloud; Apache-2.0 in the pinned repositories. Both license files are collected. |
| Whisper tiny/base converted models | SYSTRAN/faster-whisper and OpenAI Whisper, MIT. The conversion/runtime and original model notices are separate sources. |
| Kokoro 82M | hexgrad/Kokoro-82M Apache-2.0 model terms; kokoro-onnx runtime terms and speech dependencies are separate. |
| Piper en_US-ryan-high | The pinned voice MODEL_CARD identifies RyanSpeech's **CC BY-NC-SA 4.0** dataset terms. Read that card and [the linked terms](https://creativecommons.org/licenses/by-nc-sa/4.0/) before use or redistribution. Do not describe this selected voice as unrestricted commercial content. Runtime GPL terms are separate. |
| RapidOCR / selected OCR models | RapidAI / PaddleOCR model and runtime sources; Apache-2.0 metadata and collected runtime notices. Check any replacement models' own terms. |
| Gemma 3 4B GGUF and projector | Google Gemma terms and prohibited-use policy apply; Bartowski supplies the selected conversion. Read [Gemma terms](https://ai.google.dev/gemma/terms) (also collected under docs/licenses/upstream), the [prohibited-use policy](https://ai.google.dev/gemma/prohibited_use_policy) and the pinned model card. These are not BEYOND's MIT license. |
| DreamShaper 8 | Lykon's [model card](https://huggingface.co/Lykon/DreamShaper) provides model-specific conditions. The repository labels the license as Other; do not substitute the native engine's MIT license for those model terms. Read the pinned model-card snapshot and referenced original model page. |

The optional installer displays each selection's terms and requires explicit acceptance where the manifest specifies it. Choosing another model or voice requires checking that replacement's terms separately.

## Python packages

[python-packages.json](docs/licenses/python-packages.json) records all 91 distinct packages pinned across the legacy full lock, text lock and optional constraints/requirements. Each entry identifies the declared version(s), contributing requirements files, matched installed version, license metadata, project links and hashes of copied notice texts. Packages in the legacy full lock or constraints are not all installed by the text-only setup.

The snapshot collected 118 shipped notice files. Ten packages did not ship a matching notice filename in their installed distribution; upstream supplemental sources are indexed in [docs/licenses/README.md](docs/licenses/README.md). Metadata and classifier fields are retained as declared, rather than guessed or rewritten into an MIT label. These include permissive and copyleft dependencies. Blank metadata does not mean no license obligations.

To regenerate the snapshot in a fully provisioned, version-matched audit environment:

```powershell
.\.venv\Scripts\python.exe -I .\tools\license_inventory.py
```

This command only reads declared package metadata and notice files and writes documentation. It does not install anything or access the network. Missing or mismatched distributions return a nonzero status. Review removed packages/stale notice folders when updating the snapshot; the collector does not delete old notices automatically.

## Online providers and content

Search, weather, news, dictionary, movie, Wikipedia and other lookup results are supplied by their respective providers. Follow the source links shown with results. Trivia shows its source and applicable license. BEYOND's MIT license does not relicense those results, linked web pages or user-supplied files.

## Acknowledgments

Thanks to the llama.cpp, stable-diffusion.cpp, Qwen, Whisper, Kokoro, Piper, RapidOCR and Python communities, and the authors of the dependencies indexed above. Tech Jarves' [Portable Local Studio](https://github.com/techjarves/Portable-Local-Studio) was used as an external local AI engine during development. BEYOND is an independent project; this acknowledgment does not imply affiliation or endorsement.
