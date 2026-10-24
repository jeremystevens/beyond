# Releasing BEYOND

How a new version is published so that **Settings → Updates** can offer it safely. Since Phase 45, BEYOND updates
itself from GitHub releases, so the order of these steps matters: the `VERSION` file on `main` is the signal that
tells every BEYOND a new version is ready. The rules for everyday commits are in
[CONTRIBUTING.md](../CONTRIBUTING.md#keeping-updates-working).

## Version numbers

Versions are `MAJOR.MINOR.PATCH`, compared as numbers (1.10.0 is newer than 1.9.0):

| Change | Example |
|---|---|
| Fixes only | 1.1.0 → 1.1.**1** |
| New features | 1.1.0 → 1.**2**.0 |
| Big changes | 1.1.0 → **2**.0.0 |

Each release needs a new, higher number. Updates only go forward.

## Checklist

1. **Prepare the release in one commit.**
   - In `CHANGELOG.md`, turn **Unreleased** into `[x.y.z] - YYYY-MM-DD`, and start a new empty Unreleased section.
   - Write `docs/RELEASE_NOTES_x.y.z.md`. Its text becomes the GitHub release notes, which Settings → Updates shows.
   - Set `VERSION = 'x.y.z'` (keep exactly this form; the updater reads it) and `PHASE` in `app/config.py`.
   - **Don't** change the root `VERSION` file yet.
2. **Wait for GitHub's Tests workflow to pass** on that commit (both jobs).
3. **Build the release files:**
   ```powershell
   .\.venv\Scripts\python.exe tools\make_release.py
   ```
   This writes five files to `dist\release-x.y.z`, from the committed code only: `BEYOND-x.y.z-source.zip` (with
   `app-files.txt`), `Update-Beyond.ps1`, `Update-Beyond.cmd`, `SHA256SUMS.txt` and `artifact.json`.
4. **Test the update** before publishing. Install a copy of the *previous* release from its ZIP (with its own
   `.venv`, on another port), serve the new release files from this PC, and let that copy update itself through
   **Update now**. Check that it comes back on the new version with its data kept. For bigger releases, also update
   a real installation on another PC.
5. **Publish** a GitHub release with the tag `vx.y.z`, the release notes, and all five files. Then check every
   download link, and check that each file's SHA-256 matches `SHA256SUMS.txt`.
6. **Only then**, commit the root `VERSION` file as `x.y.z` on `main` and push it. From that moment, BEYOND
   installations that check for updates are offered the new version.
7. Update the README's release badge, roadmap and "latest release" mentions, if they changed.

## If a release goes wrong

- **Before step 6,** nobody has been offered it. Delete the draft or release, fix the problem, and start again.
- **After step 6,** don't delete the release. People may be updating to it, and the updater never goes back to an
  older version. Fix the problem and publish **x.y.z+1** the same way.
- An update that fails on someone's PC puts their previous version back on its own. Their log is in
  `data\updates\update-x.y.z.log`, and the result is in `data\updates\last-update.json`.

## Never

- Change the root `VERSION` file in an ordinary commit.
- Publish a release without all five files, or with a ZIP that wasn't built by `tools/make_release.py`.
- Reuse or move a tag that has already been published.
