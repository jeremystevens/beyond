# BEYOND user guide

BEYOND is a personal AI assistant you run on your Windows PC. Start with text chat, then add voice or photo tools when you want them. Chat storage and built-in AI processing stay on your PC. Web lookups, downloads and any external AI server you choose use the network.

This guide describes the setup and welcome flow on the GitHub main branch. A separate-PC installation with existing Python and optional-feature tests passed by user report. Automatic Python installation on a PC without Python remains untested. GPU acceleration is not enabled.

## 1. What you need

- Windows 10 or 11 on an Intel/AMD 64-bit PC. Windows ARM and other operating systems are not supported by the automatic installer yet.
- Internet access for Python, libraries, engines and model downloads during setup.
- Room for Python, the environment, downloads, extracted engines and your chosen model. Setup checks free space on the installation drive.
- Available RAM for loading the model. Other applications reduce currently available RAM even when the PC has plenty installed. Setup offers Retry; you can cancel and return later without closing essential work.

Python **3.14, 64-bit** is required. You do not need to install it yourself: the beginner launcher offers a verified per-user installation. Existing Python versions are preserved. BEYOND uses its own .venv folder for libraries.

## 2. Download and install text chat

1. Open [jeremystevens/beyond on GitHub](https://github.com/jeremystevens/beyond).
2. For the current setup scripts, choose **Code → Download ZIP** from the main branch. Extract the ZIP completely to a folder you can write to, such as Documents/BEYOND. Do not run from inside the ZIP. Older release archives may not contain the current installers.
3. Double-click **Setup.cmd**. If BEYOND is already running, close it normally when convenient before changing its libraries. Local AI Studio and other bots can stay running.
4. Follow the Python and isolated-environment prompts. Setup verifies the official Python installer checksum and publisher before running it. It does not remove other Python versions.
5. Choose a chat model. **Qwen3 1.7B Q8_0** is the normal starting choice, about 1.71 GiB. **Qwen3 0.6B Q8_0**, about 610 MiB, is smaller and gives simpler answers. You can choose an existing GGUF file instead.
6. Approve the chosen downloads. Setup checks the files, installs a pinned CPU engine, and generates a short test reply. Settings are saved after successful verification. An existing external AI connection is kept unless you agree to switch.
7. Accept the desktop shortcut and open BEYOND if you want. A shortcut is optional; an existing shortcut is not overwritten.

If you already have Python, you can run `py setup.py`. It finds Python 3.14 or offers the beginner bootstrap when the required version is missing. The PowerShell alternative is `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1`; the override applies to that process only.

**Do not use `pip install beyond`.** The PyPI project named beyond is unrelated to this assistant.

## 3. Open BEYOND and complete the welcome guide

Use your BEYOND desktop shortcut. If you skipped it, open PowerShell in the extracted project folder and run:

```powershell
.\.venv\Scripts\python.exe .\beyond.py
```

BEYOND runs in the system tray. Double-click its icon or choose **Open BEYOND** from its tray menu. The default chat address is [http://127.0.0.1:7770](http://127.0.0.1:7770).

On a fresh installation the welcome guide shows the model, installed RAM and available RAM. Choose **Keep current** to reuse Setup's choices. **Lighter** reduces CPU threads and conversation context; **Balanced** uses a modest context with up to eight CPU threads. Apply a changed preset before testing. An existing AI server controls its own hardware settings.

Click **Test my AI**. BEYOND requests a short greeting using the current connection; it does not include your conversations or memories. Wait for a loading model, or retry after fixing a reported problem. A successful current-configuration test unlocks **Open chat**. **Set up later** continues without marking the test passed. You can reopen the guide from **Settings → Welcome guide**.

## 4. Your first conversation

Type a question and press Send. AI answers appear as they are generated. The same conversation provides context for follow-up questions. Start a new chat to change topics; previous chats remain in the sidebar and can be renamed, reopened or deleted.

Try:

- `Explain how a rainbow forms in three short sentences.`
- `/help` to see the available commands and examples. Typing `/` opens the same command list.
- `/remember my favorite color is blue` to explicitly save a memory.

Small starter models are useful for testing and basic chat, but can make factual or reasoning mistakes. A larger model may improve answers at the cost of more memory and processing time.

### Code answers (v1.0.1)

Code in fenced blocks is displayed with preserved indentation and syntax highlighting for supported languages. Each block has **Copy code** and **Save code** controls in its header. Copy code copies only that block, without the surrounding explanation or Markdown fences. Save code downloads a text file with a suggested extension such as `.py`; your browser's download settings control the save location and whether a Save As dialog appears. The existing Copy button beneath an answer still copies the entire reply.

Controls become available when the reply finishes or is stopped. Reopened chats use the same formatting. If a model replies with unfenced code, ask it to put the example in a language-labeled code block. Unknown languages remain readable plain code. Downloading an example does not execute it; review generated code before running it.

### Recovering an interrupted reply (v1.0.1)

If an AI reply fails or its connection ends unexpectedly, a small monochrome retry icon appears with the tooltip **Retry last prompt**. It starts a fresh answer to the same question, rather than continuing at the last generated character. Partial text remains visible. Reopening the chat also offers recovery for its latest incomplete turn. If BEYOND itself is stopped, restart it before retrying. Recovery does not repeat slash commands that could change files or other state.

## 5. Everyday tools and preferences

| Where to go | What it does |
|---|---|
| Settings | AI connection, chat prompt, persona, automatic lookups, memory, popups, startup and network options. |
| Models | List, download, load, unload and switch chat models; tune each model's CPU settings. Loading a larger model needs more available RAM. |
| Status and health | See available resources, connection checks, reply speeds and recent errors. Self-test checks configuration and existing services without generating an AI reply. |
| Search history | Browse saved lookup results independently of conversations, filter them, repeat a search or delete selected entries. |
| Games | Open the built-in games; `/games` and `/help` also show the choices. |

Use **House rules** for instructions that should apply across chats, or the **Chat prompt** editor for your own assistant instructions. Long prompts take a small CPU model longer to read. Automatic fact collection and old-conversation recall can be changed in Settings. Explicit saved memories can be managed with `/memories`.

Some tools work locally; web searches, weather, news and other online lookups contact their providers. An external AI server receives the prompts and context that BEYOND sends to it. Choose a local server or the built-in engine when you want AI inference to stay on your PC.

File reading, writing and editing are limited to BEYOND's files folder and require the host PC or administrator access. Review generated code and edits before running or relying on them. See `/help` and the [README feature reference](../README.md) for exact tool syntax.

## 6. Add optional features later

Close BEYOND normally, then double-click **Add-Features.cmd**. Select the individual features you want; review each model's size and terms before approving it. Other applications can stay open if memory permits. You may skip a failed selection and continue with the others.

| Feature | What gets added |
|---|---|
| Whisper | Local microphone transcription. Choose tiny for a smaller, faster start or base for generally better accuracy. Recording never downloads a model by itself. |
| Kokoro | Spoken replies. `/speak` or the optional automatic reading setting uses the installed local voice. |
| Piper | Another local speech engine or a fallback. The selected Ryan voice has its own noncommercial dataset terms; read the notice before installing. |
| OCR | Read text in photos with local recognition models. |
| Vision | Describe or ask about photos with `/look`. Installation and a photo test passed on the separate test PC. |
| Image generation | Generate pictures with `/imagine`. CPU generation can take several minutes; installation and generation passed on the separate test PC. |

Compatibility tests run on the CPU before activating newly selected settings. Already verified unchanged selections are skipped on rerun. Use `Add-Features.cmd --retest` to retest selected features. Adding Piper does not replace an already enabled Kokoro primary voice.

See [Third-party notices](../THIRD_PARTY_NOTICES.md) for the distinction between application, engine, package, model and voice terms. BEYOND's MIT license does not replace those terms.

## 7. Use a phone or another home-network device

BEYOND must remain running on the host PC. In **Settings → Sign-in**, set a password for other devices. Turn on **Allow other devices on my network**, save and restart BEYOND when convenient. Use the address shown by Settings from a device on that network; the loopback address 127.0.0.1 refers to each device itself.

Other devices normally sign in before using BEYOND. A separate administrator password lets a trusted device manage settings and host file paths. Ordinary signed-in users do not have that access.

Browser microphones require a secure page. Follow Settings' certificate instructions and use its HTTPS address for voice recording on other devices. Install a certificate only on devices you trust and control. This guide covers home-network access; it does not require exposing BEYOND's port to the public internet.

## 8. Stop, update and back up

Closing the browser tab leaves BEYOND running. Use the tray menu's **Quit BEYOND** to close the app and its own built-in engine. It does not close your other AI applications.

Before an update or backup, quit BEYOND normally when convenient. Keep a copy of **data/** (settings, conversations, memories and other local records), **files/** (your files), and any **models/** you want to preserve. Keep backups private: they can contain personal conversations and credentials. Optional models are large and can instead be downloaded again.

For source updates, use `git pull` if you installed with Git, or extract a newer ZIP separately. Keep your old folder and private data backup until the updated copy works. Run the newer Setup.cmd to prepare its environment; do not copy a .venv between folders or PCs. Engine/model settings may reference old absolute paths, so rerun setup or choose the new paths in Settings after moving folders. Avoid replacing your data with another person's data.

## 9. If something goes wrong

| Problem | Next step |
|---|---|
| Download interrupted | Reconnect and Retry. Completed verified downloads are reused and partial downloads resume where supported. |
| Low available memory | Retry later, choose the smaller chat model during setup, or use the Lighter preset. Essential apps can stay running. |
| AI still loading | Wait for the status to become ready before testing. Large CPU models can take time. |
| AI not reachable | Check the selected mode and connection in Settings. Use Status and health for the configured service checks. |
| Port already in use | The desktop shortcut shows an error dialog; console mode prints the same explanation. Stop the known test listener or another program only when safe. To keep that program running, change BEYOND's saved web_port as described below. |
| Optional feature failed | Retry or skip it. New feature settings are not activated until its test passes. Installed libraries are not rolled back automatically. |
| Invalid .venv | Preserve it by renaming it after closing BEYOND, then rerun Setup.cmd. Do not delete chats or models. |

Read-only checks from the project folder:

```powershell
.\Setup.cmd --check
.\Add-Features.cmd --check
```

See the [setup recovery guide](../planning/setup-recovery.md) for logs and detailed recovery. Logs and settings backups can contain private paths or settings: review and redact them before posting an issue. [GitHub issues](https://github.com/jeremystevens/beyond/issues) are for bug reports; the repository's [security policy](../SECURITY.md) covers security reports.

### Changing a port when BEYOND cannot start

With BEYOND closed, back up data/settings.json, then edit its web_port field to a permitted free port.
Preserve the other JSON fields and use a number, not quoted text. If the file does not exist, create a JSON
object containing that field. Do not change app/config.py to override a saved setting.
If network access is enabled, the next port is also needed for HTTPS. Launch again after saving.
When BEYOND is accessible, future port changes are available in Settings > Address and network.

For the Phase 42 conflict test, stop the temporary Python HTTP server with Ctrl+C in its own PowerShell
window, then launch BEYOND again. The application does not close that server or other programs itself.

### If automatic Python installation fails

Manually install official Python 3.14 (64-bit) from https://www.python.org/downloads/windows/, then rerun Setup.cmd. The launcher uses the same automatic bootstrap; it is not a separate workaround. Existing-compatible-Python setup passed on the test PC; the no-Python installation path remains untested.
