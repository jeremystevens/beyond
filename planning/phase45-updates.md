# Phase 45: Easy updates

Status: built on 2026-10-24 (45A–45E): app/updates.py, Settings → Updates, installer/Update-Beyond.ps1, Update-Beyond.cmd and tools/make_release.py, with tests in tests/test_updates.py. 45F (a real 1.0.0 update on another PC) is still to do. See *Built* at the end for where it differs from the plan. Comes from item 13 of [post-v1-feature-brainstorm.md](post-v1-feature-brainstorm.md)
(high priority). Ships in the next release, which waits until more features are ready.

## Goal

Updating BEYOND should take one click. BEYOND checks the `VERSION` file on GitHub against the version it is running.
When a newer one is out, it offers it. Clicking **Update** downloads a small updater script, which downloads the new
release, swaps in the new program files, keeps everything that belongs to the user, and restarts BEYOND. If anything
goes wrong, the old version is put back.

## What the user sees

1. **A gentle notice.** When an update is available, the **Settings** button gets a small orange dot, and the
   Updates section says: *"BEYOND 1.1.0 is available. You have 1.0.1."* Only this PC and administrators see it.
   A **tray popup** also appears on this PC, once per new version: *"BEYOND 1.1.0 is available. Update now?"* with
   **Yes** and **No** buttons. **Yes** starts the update (step 4). **No** closes the popup; the dot and the
   Updates section stay, and the popup doesn't come back for that version.
2. **What's new.** The release notes for the new version, shortened, with a link to the full notes on GitHub.
3. **One button: Update now.** A short explanation first: *"BEYOND will close for about a minute, update itself
   and start again. Your chats, memories, settings, models and files are kept."* Then **Update now** or **Later**.
4. **Progress.** A small window shows the steps (downloading, checking, backing up, updating, starting). BEYOND
   reopens in the browser when it's done, with a note: *"Updated to 1.1.0."*
5. **If it fails,** the updater puts the old version back, starts it, and says what went wrong in plain words.

### Settings → Updates

- Installed version, and the result of the last check ("Up to date", "1.1.0 available", "Couldn't check: offline").
- **Check for updates** button.
- **Check automatically**: **off by default**, so BEYOND contacts GitHub only when asked. When turned on, it checks
  at most once a day, a few minutes after BEYOND starts. The **Check for updates** button works either way.
- **Update to vX.Y.Z** button, shown only when an update is available.
- Only this PC or an administrator can check or update (the existing `can_manage` rule). Ordinary signed-in devices
  never see the update controls.

## How it works

### 1. The check (inside BEYOND, Python)

- Fetch `https://raw.githubusercontent.com/jeremystevens/beyond/main/VERSION` with a short timeout. No account,
  token or personal data is sent. GitHub sees only that a request came from this PC's address.
- Compare it with `app/config.py`'s `VERSION` as version numbers, not text (1.10.0 is newer than 1.9.0).
- Offer an update only when GitHub's version is **newer**. A PC running something newer than the published version
  (a developer's copy of `main`) is never offered a "downgrade".
- A failed check (offline, GitHub down, a bad file) is quiet: it is recorded for the Updates section and never
  blocks starting up or chatting.
- The result and the time of the last check are kept in `data/updates/status.json`.

### 2. Getting the updater

- When the user clicks **Update now**, BEYOND downloads `Update-Beyond.ps1` from the matching release:
  `https://github.com/jeremystevens/beyond/releases/download/v<VERSION>/Update-Beyond.ps1`.
- It checks the file against `SHA256SUMS.txt` from the same release before running it, and also against the
  SHA-256 digest GitHub's API reports for the asset.
- BEYOND then starts the updater as a **separate process**, from BEYOND's Python backend (never from the web page),
  with `-ExecutionPolicy Bypass` for that one process only. It doesn't change any PowerShell setting on the PC.
- BEYOND then closes itself, the same way **Quit** in the tray does.

### 3. The updater (`Update-Beyond.ps1`)

A standalone PowerShell script, so it still works if BEYOND's Python environment is the thing that needs repair.

1. **Find the installation.** By default the folder it was started from, or one the user picks. Confirm it's a
   BEYOND folder (has `beyond.py`, `app\config.py` and `VERSION`) and read the installed version.
2. **Wait for BEYOND to close.** Wait for the BEYOND process from this folder to exit (and check `/api/health` stops
   answering). It never stops any other program. Local AI Studio and other bots keep running.
3. **Download and check the release.** `BEYOND-<version>-source.zip`, `SHA256SUMS.txt` and `artifact.json` from the
   release. Check the SHA-256, that `artifact.json` names the same version, and that the ZIP's own `VERSION` matches.
   Check free disk space first.
4. **Unpack into a staging folder** (`data\updates\staging-<version>`), rejecting any unsafe paths in the ZIP.
5. **Back up.** Copy the current program files into `data\updates\backup-<old version>`.
6. **Swap the program files.** Replace only BEYOND's own program files, using the list of files that belong to each
   version (see *Which files are program files* below). Files that belonged to the old version but not the new one
   are removed. Nothing outside that list is touched.
7. **Update the libraries.** Run `pip install -r requirements-lock.txt` in the existing `.venv`, plus the
   requirement file of each optional feature that's already installed (voice, OCR and so on), so optional features
   keep working. Only what changed is downloaded.
8. **Start BEYOND and check it.** Start it, wait for `/api/health` to report the new version, then open the browser.
9. **On any failure,** put the backed-up files back (and reinstall the old library versions if step 7 had run),
   start the old version, and show what went wrong. The download and backup folders are cleaned up after a
   successful update, keeping the last backup for one more update.

A log of every step goes to `data\updates\update-<version>.log`.

### What is never touched

Everything that belongs to the user lives in four folders, and the updater never deletes or overwrites anything
in them except its own `data\updates` working folder:

| Folder | Holds |
|---|---|
| `data\` | settings, chats, memories, logs, the AI engine Setup installed (`data\setup\engines`), HTTPS certificates |
| `models\` | chat models, and the voice/OCR/vision/picture models from Add Features |
| `files\` | files written from chat, and their saved versions |
| `.venv\` | the Python environment (updated by pip in step 7, never replaced) |

### Which files are program files

Every release ZIP gets a new file, `app-files.txt`: the list of program files in that version (the same files git
tracks, as in the release ZIP). The updater copies `app-files.txt` into `data\updates\installed-files.txt` after each
update, so the next update knows exactly which old files to remove.

The 1.0.0 ZIP doesn't have that list. For the first update from 1.0.0, the updater uses a 1.0.0 list built into it
(taken from `BEYOND-1.0.0-source.zip`).

### Copies made with git

If the folder is a git checkout (it has a `.git` folder), BEYOND never swaps files in it. It says
*"This copy of BEYOND was set up with git. Run `git pull`, then restart BEYOND."* This protects developers' changes,
including this PC's own copy.

### Changes to saved data

Some updates will change the database or settings layout. Each change runs once at start-up, recorded by a version
number (the way `memory.py` already uses `PRAGMA user_version`). Before running one, BEYOND copies the file it
changes into `data\updates\backup-<old version>`, so a rollback can put it back. Phase 45 adds the place for these
changes to go; it doesn't need any itself.

## For people still on 1.0.0

1.0.0 has no update check, so its users need the updater once, by hand. To keep that easy, each release also
publishes **`Update-Beyond.cmd`**, a launcher that can be double-clicked:

1. Download `Update-Beyond.cmd` from the release page into the BEYOND folder.
2. Double-click it. It downloads and checks `Update-Beyond.ps1`, then runs it.

The README and the release notes explain this in two lines. From the next version on, updates come from
Settings.

## Changes to how releases are published

A release now publishes, in this order:

1. The release ZIP (now including `app-files.txt`), `SHA256SUMS.txt` (covering all files below), `artifact.json`,
   `Update-Beyond.ps1` and `Update-Beyond.cmd`.
2. Check every download link and checksum on the published release.
3. **Only then** change `VERSION` on `main` to the new version. That's the moment users are offered it. Ordinary
   commits to `main` never change `VERSION`, so they never trigger an update.

A small release script (`tools/make_release.py`) builds the ZIP, the file list and the checksums, so this is the
same every time.

## Security and privacy

- The update check is one plain HTTPS request for a public file. It sends no account, token, chat or personal data.
- Downloads come only from `github.com/jeremystevens/beyond` over HTTPS and are checked against SHA-256 before use.
  This protects against broken or tampered downloads, but not against someone who controls the GitHub account
  itself. Signing releases is noted as a later step.
- Installing is always started by a person (this PC or an administrator). Checking can be automatic; updating
  never is.
- The updater refuses ZIP entries that would write outside the BEYOND folder.

## Steps

| Step | What | Done when |
|---|---|---|
| **45A · Check** | Version comparison, the GitHub check, `data\updates\status.json`, optional daily automatic check (off by default), `/api/updates` (check and status), admin-only rules | Tests cover newer/older/equal/bad versions, offline and timeouts, and only this PC or an administrator can check |
| **45B · Settings → Updates** | The Updates section, the dot on the Settings button, release notes, the confirmation, optional tray popup | Works on desktop and phone, light and dark |
| **45C · Updater** | `Update-Beyond.ps1` and `Update-Beyond.cmd`: wait, download, verify, back up, swap, pip, start, roll back | A fake release on a local test server updates a copy of BEYOND, keeps its data, and rolls back when a step is made to fail |
| **45D · Launch from BEYOND** | Download and verify the updater, start it as its own process, close BEYOND | Clicking **Update now** on a test copy updates it and it comes back on the new version |
| **45E · Release tooling and docs** | `tools/make_release.py`, `app-files.txt`, the release checklist, README and User Guide sections, the 1.0.0 instructions | A dry-run release builds every asset with matching checksums |
| **45F · Real test** | Update a real 1.0.0 installation on a separate PC to the new version | Chats, memories, settings, models and optional features all still work; an unplugged network mid-download and a forced failure both leave a working BEYOND |

## Decisions (all answered 2026-10-24)

1. ~~**The next version number**~~ **Decided:** the next release is **1.1.0**, not 1.0.1, because it bundles
   several features (code blocks, retry, updates and more). When it's prepared, `app/config.py`, the CHANGELOG's
   Unreleased section and `docs/RELEASE_NOTES_1.0.1.md` become 1.1.0. `VERSION` changes only after it's published.
2. ~~**Tray popup** for a new version~~ **Decided:** yes, a popup with Yes and No buttons (see *What the user sees*).
3. ~~**Automatic checks on by default**~~ **Decided:** off by default. Users can turn on a daily check, and the
   Check for updates button is always there.
4. ~~**The git-checkout case**~~ **Decided:** message only. BEYOND never runs git itself; developers run
   `git pull` when they choose. This matters on PCs where several people or tools work in the same git copy.

## Not in this phase

- Automatic installing without a click.
- Downgrading to an older version (the backup only covers the last update).
- Updating models or the AI engine (Setup and Add Features already handle those).
- Signed releases.

## Built (2026-10-24): differences from the plan

- **Libraries:** the updater installs `requirements-text-lock.txt` (what Setup installs) plus the requirement file of
  each optional feature that passed its test in `data\setup\optional\features.json`, and only when one of those
  files changed. Before pip runs it saves `pip freeze`, which a rollback reinstalls.
- **The old version's files:** after each update the list is kept in `data\updates\installed-files.txt`. For the first
  update (from 1.0.0, or any version without that list) the updater downloads that version's own release ZIP, checks
  it, and reads its file list. No list is built into the script. If it can't, files the new version dropped are
  simply left in place.
- **Version check of the download:** the updater checks the version in the ZIP's `app\config.py`, because a release
  commit's `VERSION` file is only changed after publishing. `tools/make_release.py` also writes the release version
  into the ZIP's `VERSION`.
- **Progress window:** the updater runs in its own console window with numbered steps (1–8), and logs to
  `data\updates\update-<version>.log`. The result goes to `data\updates\last-update.json`, which Settings shows.
- **Tray popup:** only after an automatic check (a manual check is already on screen). Clicking **Yes** starts the
  update; **No** closes it for that version.
