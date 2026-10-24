# Phase 48: Conversation attachments

Status: built on 2026-10-24: one 📎 button, only the extracted text kept, 20 MB and 5 documents per chat. From item 10 of [post-v1-feature-brainstorm.md](post-v1-feature-brainstorm.md);
the headline feature of 1.1.0.

## Goal

Drop a PDF or document into a chat and talk about it: "summarise this", "what does page 4 say about the warranty?",
"compare the two quotes". It stays attached to that chat, so follow-up questions can use it without attaching it again.

## What the user sees

1. **Attach.** The 📷 button becomes 📎 **Attach a photo or document**, and dropping a file on the chat works too.
   Photos keep doing what they do now (`/scan`, `/look`). Documents are attached to the chat:
   *"📎 Attached **warranty.pdf** · 12 pages · ✕"*. With no chat open yet, a new chat starts, named after the file.
2. **Ask.** Every message in that chat can use what's attached. Answers mention the page they used ("page 4 says…").
3. **See what's attached.** A small line at the top of the chat: *"📎 warranty.pdf · quote-A.docx"*.
4. **Remove.** ✕ on the attachment note detaches it: BEYOND stops using it, and its text is deleted.

## Which files

| Type | How the text is read |
|---|---|
| **PDF** (.pdf) | `pypdf`, page by page, so answers can name pages. Scanned PDFs (pictures of pages) have no text to read: BEYOND says so and suggests photographing a page for `/scan` |
| **Word** (.docx) | Read directly from the file (a .docx is a ZIP of XML), no extra library. Old .doc files aren't supported |
| **Text and code** (.txt .md .csv .json .html .xml .log .py .js …) | As text (UTF-8, UTF-16 or Windows encoding) |

Limits: up to **20 MB** per file, **5 documents** per chat, and up to **1,000,000 characters** of text per document
(about 300 pages). Password-protected PDFs are refused with a plain message.

## How the AI uses a document (small models, CPU)

The AI on a CPU has a small context (8,192 tokens by default), so a big document can't be sent whole with every
question.

- **Short documents** (up to about 9,000 characters, a few pages): the whole text goes with each question.
- **Longer documents** are split into passages of about 1,500 characters, each remembering its page. For each
  question, BEYOND picks the passages that best match it (a keyword search over the passages, the same kind of
  search memory recall uses) and sends those, up to about 9,000 characters across all attachments, labelled with
  file name and page.
- **"Summarise this"** on a long document: BEYOND sends the opening passages plus the passages that look like headings
  and conclusions, and tells the AI it is seeing parts of a longer document, so the answer doesn't claim to cover
  everything.
- The text is marked as **data, not instructions** (like file reading), and the AI is asked to name the page it used
  and to say when the document doesn't answer the question.
- No extra AI call: one normal reply per question.

## Storage, privacy and other features

- Only the **extracted text** is kept, in BEYOND's database (`data\`), never sent anywhere. The original file isn't
  stored. Deleting the chat or pressing ✕ deletes the text.
- **Branches** (Phase 47) take along the attachments of the messages they copy.
- **Search history, memory recall and fact pickup** don't search attachment text.
- **Other devices** can attach documents to their chats, like photos. It's limited to the chat, not BEYOND's files
  folder.
- **New library:** `pypdf` 6.21.2 (BSD-3-Clause, pure Python, no further dependencies), added to
  `requirements-text-lock.txt`, the other requirement files and the licence notices. The updater installs it
  automatically on update.

## Steps

| Step | Done when |
|---|---|
| Reading PDFs, Word and text files into pages and passages | Tests with real sample files cover each type, pages, encodings, empty/scanned PDFs, password-protected PDFs, bad and oversized files |
| Database, API (attach, list, remove), branches and chat deletion | Tests cover limits, removal, copying into branches, deleting chats |
| Picking passages for each question | Tests check the right passages and pages are chosen within the size limit, and short documents go whole |
| The page: 📎 button, drop, the note with ✕, the line at the top | Works on desktop and phone, light and dark |
| Real check | A real PDF and Word file, questions about specific pages, a summary, and a follow-up, with the 3B/4B models |
| Docs | README, User Guide, CHANGELOG, licence notices, phases.md |

## Decisions (answered 2026-10-24)

1. **One 📎 button** for photos and documents (replacing 📷), or keep 📷 and add a separate 📎?
2. **Keep only the extracted text** (the plan: smaller and more private), or also keep the original file so it can be
   downloaded again from the chat?
3. **Limits:** 20 MB per file and 5 documents per chat, OK?

Answers: one 📎 button replacing 📷; keep only the extracted text; 20 MB per file and 5 documents per chat. The attachment tables are created with the chat tables in `app/chats.py`, so every part of BEYOND that opens the chat database has them.
