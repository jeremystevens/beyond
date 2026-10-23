# Phase 43 release preparation

Status: BEYOND 1.0.0 published and verified. Release source commit: d01be62473a235230bbc42e037ea7180547d2b6d.

## Decisions carried forward

- Proceed with preparation despite the explicitly untested no-Python bootstrap, as Jeremy requested.
- Do not call Setup.cmd an alternate bootstrap workaround. Document manual Python 3.14 x64 installation first.
- Preserve verified separate-PC results and distinguish them from missing raw logs/revision metadata.
- Source-only release initially: do not bundle .venv, user data, weights or native engines without a separate artifact audit.

## Release checklist

- [x] Record Phase 42 reports and disclose outstanding cases.
- [x] Prepare docs/RELEASE_NOTES.md and manual-Python fallback.
- [x] Set release candidate version 1.0.0 / phase 43; draft tag v1.0.0. Publication remains pending.
- [x] Run final regression checks at the exact release commit.
- [x] Build a source ZIP from that commit's tracked files, excluding local/runtime material.
- [x] Inspect archive paths and contents; record SHA-256, size and commit.
- [x] Review exact artifact notices, including dependencies/models fetched by setup and any incorporated native components.
- [x] Verify user-facing guide/README links and remove obsolete validation claims.
- [x] Publish the final release/tag and upload the reviewed artifact when ready.

No live application restart, setting change or external courtesy message is part of this preparation.

## Published artifact

Release: https://github.com/jeremystevens/beyond/releases/tag/v1.0.0

Full Windows/Python 3.14 test run: https://github.com/jeremystevens/beyond/actions/runs/39880607384 (passed).

Source ZIP: BEYOND-1.0.0-source.zip; 1786797 bytes; 608 entries.

SHA-256: 45f7046d6dd632baf895533082106be277c0ba8cf4de4a3d7b3acd19ed663f3f

The public tag resolves to the passing source commit, all three uploaded asset digests match their local files, and v1.0.0 is GitHub's latest release. The source archive was audited for private/runtime directories, binaries and all collected notice hashes. It does not redistribute downloaded engines, models or the installed Python environment. Phase 42 exceptions remain disclosed in the release notes.
