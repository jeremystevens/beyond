# BEYOND 1.1.0

The first feature release since 1.0.0. BEYOND can now **update itself**, read the **documents** you attach, take a
conversation in a **new direction** without losing it, and **rework an answer** with one click. Everything still runs
on your own PC.

## What's new

**📎 Attach documents to a chat**
Press the paper clip, or drop a file on the chat, to attach a **PDF**, **Word (.docx)** or **text/code** file (up to
20 MB, 5 per chat). Then ask about it: "summarise this", "what does page 4 say about the warranty?", "compare the two
quotes". The document stays with the chat for follow-up questions, and answers name the page they used. Long
documents work too: BEYOND sends the parts that best match each question, so a small AI on a processor can cope.
Only the text is kept, on your PC, and ✕ removes it. Photos attached the same way still read text or answer
questions about the photo.

**⑂ Branch a conversation**
Press ⑂ under any answer to continue from that point in a new chat: camping in one branch, hotels in another. The
original stays as it was, and each branch links back to it.

**✨ Adjust this answer**
Under the newest answer, ✨ offers **Simpler**, **More detail**, **Show an example** and **Walk me through it**, so you
get a better follow-up without writing a new prompt.

**⬆ Easy updates**
**Settings → Updates** checks GitHub for a newer version and updates BEYOND with one click. It keeps your chats,
memories, settings, models and files, and puts the previous version back if anything goes wrong. Checking is off
until you press **Check for updates** or turn on the daily check, which also asks with a popup when a new version is
out.

**Code answers**
Code appears in its own blocks with syntax highlighting, and each block has **Copy code** and **Save code**, so the
explanation around it never ends up in your editor.

**Smaller things**
- A quiet retry icon appears when a reply is interrupted, and BEYOND notices when a reply stops unexpectedly.
- The attach and microphone buttons use standard paper clip and microphone icons.
- Error messages say what went wrong when a document can't be attached.
- Database connections are closed properly. Nothing visible changes, but a long-running BEYOND leaves no connections open.

## Updating

- **From 1.0.2** (the updater test release): **Settings → Updates → Check for updates → Update to 1.1.0**.
- **From 1.0.0:** download **Update-Beyond.cmd** from this release into your BEYOND folder (next to `beyond.py`) and
  double-click it. Quit BEYOND from its tray icon first.
- **If you set BEYOND up with git:** run `git pull`, then restart BEYOND.

The update installs one new library, **pypdf** (for reading PDFs), into BEYOND's own Python environment, so it needs
an internet connection. Your data, models and optional features are kept. The database gets a few new columns and
tables when 1.1.0 first starts; your existing chats are unchanged, and an older version can still read them.

Full details are in the [CHANGELOG](../CHANGELOG.md).

## Known limits

- Scanned PDFs (pictures of pages) have no text to read: photograph a page and attach the photo instead.
  Password-protected PDFs and old .doc files aren't supported.
- On long documents, "summarise this" covers the opening and the headings, not every page.
- The limits from 1.0.0 remain: automatic Python installation on a PC without Python hasn't been tested end to end
  (install Python 3.14 x64 yourself, then run Setup.cmd), and Piper on a separate PC is unconfirmed.
