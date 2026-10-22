# Phase 41: guide, notices and project identity

**Date:** 2026-10-21
**Status:** Documentation and notice inventory prepared; fresh-machine walkthrough and release-artifact review remain pending.

## Deliverables

- docs/USER_GUIDE.md: GitHub ZIP download, Python/bootstrap, text-model choice, launch, welcome presets/test, everyday use, optional features, home-network access, backups, updates and recovery.
- THIRD_PARTY_NOTICES.md and docs/licenses/: application/engine/package/model/voice distinctions, copied notice texts and source/hash provenance.
- tools/license_inventory.py: offline collection of declared pins and version-matched installed metadata/notices. Does not install packages or load application data.
- README: guide/notices navigation, accurate local-versus-network privacy description and package-name distinction.
- Piper optional manifest: explicit RyanSpeech CC BY-NC-SA 4.0 dataset label, separate from runtime GPL-3.0-or-later; payload pins unchanged.
- planning/tech-jarves-courtesy-note.md: draft acknowledgment message, not sent. No message, issue or contact action is authorized by this phase alone.

## Name check

Checked 2026-10-21:

- The existing project is https://github.com/jeremystevens/beyond. GitHub repository names are scoped to their owners; the exact-name search is not exclusive ownership of the word.
- https://api.github.com/search/repositories?q=beyond+in:name&per_page=4 returned many existing repositories (28,251 at retrieval), including zhoushuguang/beyond, presbrey/beyond, wesovilabs/beyond and galactics/beyond. Counts and rankings change.
- https://pypi.org/project/beyond/ is an existing unrelated flight-dynamics/space-observation package. Do not publish or tell users to install this assistant under that occupied package name. The guide uses the GitHub ZIP and Setup.cmd.
- This is a repository/package-name check, not a trademark clearance or a reservation of a future distribution name. BEYOND's current project name and repository were preserved.

## Notice collection

91 distinct declared Python packages matched installed versions across the full/text locks and optional constraints/requirements. Collected 118 shipped notice texts. Ten distributions lacked a matching notice filename; supplemental upstream license snapshots and metadata identify those gaps. Default-branch snapshots are labeled separately from release-tag sources. Source URLs and SHA-256 values accompany upstream materials. Git attributes preserve notice bytes across checkout so those hashes remain stable.

Native engines, Python and model notices are separate from the package inventory. Piper's selected voice card identifies noncommercial dataset terms; DreamShaper is labeled Other and refers to its original model page; Gemma has its own terms/policy. No dependency or model is relabeled MIT because BEYOND uses MIT.

## Acceptance and release follow-up

Validate relative documentation links, inventory pin coverage, file existence/checksums, upstream provenance, and the unchanged model payload pins. Run optional-installer checks after the license-label change. This phase makes no app/runtime changes and does not require stopping the running bots or work sessions.

Phase 42 still needs a real clean-PC install/welcome walkthrough, the no-Python case, port conflict and pinned vision/image inference. Phase 43 must inventory the exact release artifact, including incorporated native libraries (for example FFmpeg/eSpeak), preserve their notices/source obligations, and recheck model/version-specific terms before bundling binaries or weights. The current source checkout has no model weights or native executables. The courtesy note stays a draft until Jeremy explicitly chooses to send it.

## Verification result

Passed: 32 authored relative documentation links; all 91 package versions matched; all 118 shipped-notice checksums and 19 upstream snapshot checksums verified. Optional-feature payload URLs/sizes/hashes were compared with HEAD and remained unchanged; only the Piper license display label changed. All 11 optional-installer tests passed. No dependency installation, model inference, application restart or external message was performed for this phase. The complete binary-artifact licensing review remains explicitly separate from this source documentation milestone.
