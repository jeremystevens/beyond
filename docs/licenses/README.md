# Collected license materials

Start with [Third-party notices](../../THIRD_PARTY_NOTICES.md) for the overview. BEYOND's own [MIT license](../../LICENSE) is separate.

[python-packages.json](python-packages.json) lists 91 declared pinned packages and 118 notice files copied from matching installed distributions under python/. Each file has its SHA-256 recorded. This is the union of the legacy full lock, text lock and optional constraints/requirements, not the set installed by text-only setup.

Ten distributions shipped no matching notice filename. Their metadata remains indexed, with supplemental sources below:

| Distribution | Supplemental notice |
|---|---|
| ctranslate2 | [CTranslate2 LICENSE](upstream/CTranslate2-LICENSE.txt), resolved from v4.8.2 |
| flatbuffers | [FlatBuffers LICENSE](upstream/flatbuffers-LICENSE.txt), resolved from v25.12.19 |
| tokenizers | [Tokenizers LICENSE](upstream/tokenizers-LICENSE.txt), resolved from v0.23.3 |
| primp | [Primp LICENSE](upstream/primp-LICENSE.txt), upstream branch snapshot |
| espeakng-loader | [Loader LICENSE](upstream/espeakng-loader-LICENSE.txt), plus [eSpeak NG COPYING](upstream/espeak-ng-COPYING.txt) |
| winrt-runtime and four winrt-Windows.* packages | [PyWinRT LICENSE](upstream/pywinrt-LICENSE.txt), upstream branch snapshot; installed metadata declares MIT |

A branch snapshot is not represented as a release-tag match. Retain exact wheels' incorporated-library notices when distributing an environment.

The upstream/ folder also contains Python, native engine and Qwen licenses, Whisper/Kokoro notices, and pinned Piper, DreamShaper and Gemma conversion model cards. [upstream/sources.json](upstream/sources.json) records URLs, revisions where available and SHA-256 values. Mutable source URLs are labeled explicitly.

Read Gemma's [terms](https://ai.google.dev/gemma/terms) and [policy](https://ai.google.dev/gemma/prohibited_use_policy), DreamShaper's referenced original model page and voice terms with these snapshots. Final executable/archive license review remains a Phase 43 release item.

Regenerate Python notices with [tools/license_inventory.py](../../tools/license_inventory.py) in a version-matched audit environment. It performs no installation or network access. Review stale notices when pins change.
