# Setup recovery

Setup installs text chat. Add-Features installs only your selected extras. Both can be rerun after a failure.
Keep chats, models and settings; do not delete the whole project to start again.

| What happened | What to do |
|---|---|
| Internet connection dropped | Reconnect and choose Retry. Verified completed files are reused; partial model downloads resume when the server supports it. |
| Not enough free memory | Retry later or cancel and return later. Installed RAM and currently available RAM are different. You do not have to close essential work sessions. |
| Not enough disk space | Free space on the installation drive, then Retry. Allow room for downloads, extracted engines and libraries. |
| A library install failed or timed out | Read the log path shown on screen, check memory/connection, then Retry or rerun the launcher. Only its owned worker processes are stopped. Installed packages are checked again. |
| Existing model/engine failed verification | Preserve your own copy. Move the named file or engine folder aside, then Retry to obtain a verified replacement. Do not disable verification. |
| Existing .venv is invalid | Close BEYOND normally when convenient. Rename .venv to .venv-backup, then rerun Setup.cmd. Keep the backup until the replacement works. Other Python installations are untouched. |
| Another setup is running | Finish or cancel that installer first. The file lock releases when its process exits; do not delete the lock file while an installer runs. |
| Port is busy / BEYOND is running | Cancel and return when BEYOND can be closed normally. Setup does not stop the program using the port. Other apps can remain running. |
| Settings changed during setup | The newer settings are preserved. Rerun setup to work from the latest configuration. |
| Optional feature failed | Retry, skip that feature, or cancel the remaining selections. Failed tests do not activate new settings; other selections can continue. |
| CPU instructions unsupported | A compatible native engine build is needed. A smaller model cannot fix missing CPU instructions. |

Press Ctrl+C to cancel. Completed downloads and saved settings remain available. An interrupted package installation may require another run before launching BEYOND. Optional-feature installation is not a package rollback: libraries already installed remain installed.

Read-only checks:

```powershell
.\Setup.cmd --check
.\Add-Features.cmd --check
```

Run Add-Features.cmd with --retest to retest a previously verified selection. No feature is enabled until its compatibility test passes. GPU acceleration is not enabled by these installers.

Logs are local under data/setup/: install.log for steps, libraries.log and libraries-check.log for text packages, app-test.log for startup and chat-test.log for the chat engine. Optional package logs and feature worker results are under data/setup/optional/. Settings backups use settings-before-*.json; treat these as private and do not post them publicly.

Fresh-machine acceptance still needs a Windows installation without Python, text setup from scratch, optional features one at a time, and the port-conflict check. Jeremy will run the pending pinned vision and DreamShaper inference tests there; the busy development PC's essential apps and other work sessions remain running. These checks are deferred, not passed.
