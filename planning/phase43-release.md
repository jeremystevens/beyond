# Phase 43 release preparation

Status: draft materials prepared; release not published.

## Decisions carried forward

- Proceed with preparation despite the explicitly untested no-Python bootstrap, as Jeremy requested.
- Do not call Setup.cmd an alternate bootstrap workaround. Document manual Python 3.14 x64 installation first.
- Preserve verified separate-PC results and distinguish them from missing raw logs/revision metadata.
- Source-only release initially: do not bundle .venv, user data, weights or native engines without a separate artifact audit.

## Release checklist

- [x] Record Phase 42 reports and disclose outstanding cases.
- [x] Prepare docs/RELEASE_NOTES.md and manual-Python fallback.
- [x] Set release candidate version 1.0.0 / phase 43; draft tag v1.0.0. Publication remains pending.
- [ ] Run final regression checks at the exact release commit.
- [ ] Build a source ZIP from that commit's tracked files, excluding local/runtime material.
- [ ] Inspect archive paths and contents; record SHA-256, size and commit.
- [ ] Review exact artifact notices, including dependencies/models fetched by setup and any incorporated native components.
- [ ] Verify user-facing guide/README links and remove obsolete validation claims.
- [ ] Publish the final release/tag and upload the reviewed artifact when ready.

No live application restart, setting change or external courtesy message is part of this preparation.
