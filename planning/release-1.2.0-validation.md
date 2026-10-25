# Release 1.2.0 validation

Release procedure: docs/RELEASING.md. Includes Phases 49–53. Root VERSION is changed only after publication/download verification.

Completed:

- Initial candidate c1cb66a passed Windows/Python 3.14 and Chromium CI (40168212921). The Windows fixture fix candidate 174914e passed both jobs (40168726130), then the main push also passed (40169012814).
- Built all five assets from committed 174914e using tools/make_release.py. Verified archive VERSION/config 1.2.0, manifest and commit metadata.
- Installed the published 1.1.0 ZIP in a separate directory with its own newly installed Python environment and sample chat, memory, settings and data/model/file markers. Used the actual Update now API with a loopback asset fixture and the unchanged release updater (test DownloadBase/VersionUrl arguments supplied by the harness).
- Final-package 1.1.0 → 1.2.0 upgrade and automatic restart passed. Actual sample chat/memory/custom setting and markers were preserved; the existing independent environment remained. The validation copy was stopped without closing unrelated apps. Test harness fixes covered Windows asyncio import order and owned relative beyond.py process arguments; production updater files were unchanged.
- A real read-only GitHub lookup in the isolated updated app returned checked=true and a bounded draft URL. No public issue was created. Mock tests also cover matches, rate limits/offline behavior, simulated entries and long reports; browser tests cover handoff invalidation and safe literal match rendering.
- Published v1.2.0 with all five files. Downloaded the staged assets and checked exact hashes, then verified every public download returned HTTP 200 and matched both the built files and GitHub digests. Details are retained locally in data/setup/release12-public-verification.json.
- Root VERSION is now advanced only after publication/verification. README badge, roadmap, changelog, user guide and release notes describe 1.2.0 and Phases 49–53.
- Upgrade validation used an isolated real installation on the same Windows host; no second physical computer update was performed.

A prior main push (40167242771) failed in the Windows job-object fixture: it read child.pid between file creation and PID content publication. The fixture now publishes the PID atomically and verifies actual child exit with a bounded wait (retained Windows handles need not imply a running process). Parent/child cleanup assertions remain active. This is a test-readiness fix; production process ownership is unchanged.
