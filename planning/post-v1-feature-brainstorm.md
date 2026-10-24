# BEYOND: Post-v1.0 Feature Brainstorm

Started: 2026-10-23
Status: Open brainstorming. Jeremy liked the five end-user ideas below; implementation scope, priority, and roadmap phases are not yet approved. Keep adding ideas here as discussion continues.

## Direction

Focus on useful, interesting features for everyday users. Check current capabilities and earlier rejected proposals before adding candidates. Preserve responsiveness on CPU-only systems and small local models.

## End-user candidates

### 1. Conversation branches

Branch from a selected message into a separate chat containing the conversation up to that point. Continue exploring another approach while preserving the original chat. Link branches to their original conversation for easy navigation.

Example: Explore camping in one vacation-planning branch and hotels in another.

To discuss: branch naming, navigation, copied attachments, and how memories and house rules apply.

### 2. Pick up where we left off

When reopening a long chat, offer a short recap of decisions, unfinished questions, and the next step. Ground the recap in the conversation and let the user request or refresh it.

To discuss: when to generate recaps, caching, and the CPU cost of summarizing long chats.

### 3. Voice conversation mode

Continue speaking with BEYOND without pressing microphone and playback buttons for every exchange. Build on the existing Whisper input and spoken replies for a casual conversation without typing. Jeremy explicitly supported this candidate and expanded it with optional transcription/logging.

- Start and end an explicit voice conversation session; listen for the next turn and play replies automatically while the session is active.
- Whisper transcribes the user's speech for input and, when selected, the conversation log. Piper or Kokoro provides BEYOND's spoken output; capture its original reply text directly for the log rather than transcribing playback.
- Offer separate choices to show a live transcript and keep a session transcript for saving. Hiding the transcript should still allow an opted-in session log to be saved afterward.
- After ending the session, offer to save the entire conversation to a text file with You and BEYOND speaker labels.
- Include microphone pause and clear listening/speaking indicators. Prevent the microphone from treating BEYOND's own playback as user speech.

To discuss: silence detection, interruption, speaker feedback, CPU/memory use, transcript correction, and retention/deletion of unsaved logs. Clarify that Whisper transcription is required for understanding voice input; optional logging controls whether that text is retained/exported. Raw audio recording is not requested.

### 4. Side-by-side comparisons

Build an editable comparison from a conversation using criteria the user chooses. Examples include apartments, vacation plans, and job offers. Distinguish user-provided facts from AI suggestions and unknown information.

To discuss: editing criteria and values, saving comparisons, and whether a dedicated view adds value beyond a chat table.

### 5. Adjust this answer

Offer actions such as Simpler, More detail, Show an example, and Walk me through it on an answer. Users can request a useful follow-up without composing another prompt.

To discuss: which actions appear, how the result joins the conversation, and interaction with existing rewrite features.

## Additional discussion candidates

### 6. Error tracking and recovery

Jeremy noted that PromptetheusBot has built-in error tracking that BEYOND lacks. Explore capturing failures and giving users a clear message with Retry, View details, and Copy error report where appropriate.

Inspect BEYOND's existing logging and PromptetheusBot's implementation before defining the gap. Keep reports free of secrets and unnecessary conversation content. Retry only operations that can safely be repeated.

Expansion requested by Jeremy: optional reporting to the main project's GitHub issue tracker so maintainers can investigate, repair problems through pull requests, and deliver fixes in updates.

- Capture errors locally with the BEYOND version and relevant diagnostic details.
- Provide an optional Report a problem action with a cleaned report the user can preview before submission.
- Exclude chats, passwords, tokens, and personal file paths by default.
- Check for existing reports and consolidate repeat errors rather than creating duplicate issues.
- Proposed repair workflow: report, investigate, create a fix in a pull request, test, and release an update. Reporting does not guarantee an immediate or automatic fix.
- Explore a submission option for users without a GitHub account. Never embed a shared GitHub access token in the distributed app.

Open questions: submission/authentication design, diagnostic fields and redaction, duplicate matching, and how users follow issue and fix status. This remains a brainstorming candidate, not an approved implementation plan.

### 7. Mood-aware chat replies

Jeremy is interested in recognizing apparent mood during conversation, provided replies remain near their current speed. Adjust tone subtly: clearer, shorter steps for frustration; warmer replies for excitement. Avoid repeatedly announcing inferred moods.

Preferred starting approach: a short instruction in the existing chat request, without a separate AI classification call or extra model. Mood is tentative context, not a diagnosis. Persistent mood history is not part of the proposed starting scope.

Before approval, compare latency and response quality with the instruction enabled and disabled, including the 0.6B model. No performance guarantee has been established.

## Additional end-user candidates selected by Jeremy

Selected for inclusion in these notes on 2026-10-23. Release scope, priority, and implementation phases remain to be decided in a separate roadmap. No additional games are wanted; focus future brainstorming on everyday usefulness.

### 8. Search your own documents

Choose a folder of manuals, PDFs, or reference material, then ask questions with answers linked to the source passages. Help users find information in their own material without manually searching every file.

Example: Ask what a device manual says about a warning light and open the supporting passage.

Overlap check: extends existing file-reading tools into a searchable document collection with source references. Inspect current document support before defining implementation scope.

To discuss: supported formats, scanned PDFs, explicit folder selection, indexing and refresh, local storage, CPU/RAM costs, and how to handle missing or conflicting evidence.

### 9. Screenshot troubleshooting

Paste an error screenshot and ask what happened and what to try. Combine the existing image tools with guided troubleshooting that explains the visible error and proposes clear next steps.

Overlap check: builds on existing OCR and vision rather than adding another generic image-description command. Relate this to error reporting where useful, while retaining support for screenshots from other applications.

To discuss: OCR versus vision requirements, confirming uncertain text, asking for missing context, and user-controlled troubleshooting steps. Screenshot content may include private information.

### 10. Conversation attachments

Drop a PDF or document into a chat and discuss it, compare sections, or extract specific information. Keep the attachment available as context for follow-up questions in that conversation.

Overlap check: differs from a persistent searchable folder by focusing on documents attached to a particular chat. Explore shared parsing and source-reference support with Search your own documents.

To discuss: supported formats and size limits, page/section references, large-document handling on small local models, attachment retention/deletion, and behavior when branching chats.

### 11. Expanded /rewrite and guided writing helper

Selected by Jeremy for inclusion in these notes. Expand /rewrite beyond basic tone changes with a guided helper similar to the /imagine helper. Keep /rewrite available as a quick command and offer guided drafting for users who want help choosing an approach.

Writing tasks:

- Reply to an email: paste the original, describe the intended response, and choose a tone.
- Polish existing writing: improve clarity, grammar, and professionalism while preserving meaning.
- Draft documents: letters, announcements, reports, proposals, and other structured material.
- Rewrite or explain material for a particular audience and level of technical knowledge.

Tone and style choices:

| Tone or style | Typical use |
| --- | --- |
| Casual | Relaxed everyday messages |
| Professional | Workplace emails and documents |
| Friendly | Approachable correspondence |
| Technical and precise | Specifications, engineering notes, API documentation |
| Plain language | Complex material explained for a general audience |
| Formal | Official letters, policies, proposals |
| Diplomatic | Disagreements, complaints, sensitive feedback |
| Firm and assertive | Boundaries and requests for action |
| Warm and empathetic | Support replies and personal messages |
| Persuasive | Proposals, pitches, requests |
| Instructional | Tutorials, procedures, training material |
| Academic | Structured explanations and research-style writing |
| Concise and direct | Brief updates, summaries, announcements |

Helper inputs: intended audience, purpose, required details, tone, document type, and detail level. Avoid making users fill every field when a simple request is sufficient. Proposed output actions: Copy and Revise, with Download to explore alongside document export support.

Technical-document options:

- Types: technical specification, README, troubleshooting guide, installation guide, API reference, and incident report.
- Audiences: beginner, technician, developer, or engineer.
- Sources: attached specifications, existing documentation, code, and user notes.
- Detail levels: overview, practical instructions, or comprehensive reference.
- Use appropriate technical terminology and preserve supplied specifications, units, versions, and requirements. Do not invent specifications or citations; mark missing details as needing confirmation or ask the user.

Example: Turn these notes into a technical installation guide for experienced Windows administrators, including prerequisites, configuration, verification, and troubleshooting.

Overlap check: extends existing /rewrite with guided drafting and document structure rather than replacing the quick command. Coordinate with conversation attachments for source material and Adjust this answer for follow-up actions.

To discuss: current supported tones, helper layout, combining tone with document type and audience, long-document handling, and export formats. Inclusion in these notes does not assign a release phase.

### 12. Code blocks with syntax highlighting and independent Copy/Save controls

HIGH PRIORITY: Jeremy explicitly requested this be one of the first items added/fixed in the next roadmap. It addresses a practical usability problem when taking generated code into an editor. Exact release phase remains to be assigned.

Reported behavior: a request such as a simple Python class example does not produce a properly highlighted code block. The existing bottom Copy button copies the entire reply, including explanatory prose, which can break code when pasted into an editor.

Required experience:

- Render code in distinct blocks with preserved indentation and line breaks, syntax highlighting, and a language label when known.
- Encourage the model to put generated code in proper fenced code blocks; inspect current prompting and rendering before defining the fix.
- Give each block its own small Copy code button in the upper-right corner. Copy only that block's code, excluding explanation, language labels, controls, and Markdown fences.
- Give each block a Save code action with an appropriate suggested filename/extension, such as example.py. Browser download settings determine whether a Save As dialog appears; do not promise a native dialog in every browser.
- Multiple code blocks have independent controls. Preserve the existing whole-reply Copy action for users who want the full response.

Validation to cover: exact copied/downloaded content, Python indentation, multiple blocks, unknown languages, streamed and reopened replies, and safe rendering of code containing HTML/script text. Review current renderer support and local/offline highlighting options during planning.

### 13. Simple software updating with VERSION checks

HIGH PRIORITY: Jeremy requested easy upgrades for existing users without deleting their installation or starting over. Plan alongside code-block improvements as an early release priority; implementation remains for the separate roadmap.

Version discovery and user experience:

- Add a root VERSION file to the main GitHub repository and keep it consistent with the application's installed version.
- Compare the installed version with the published VERSION using proper version-number comparison (for example, 1.10.0 is newer than 1.9.0).
- Update the public VERSION only when the matching release and assets are published and available. Development commits must not trigger premature upgrade offers.
- Check in the background, offer a manual Check for updates button, and allow automatic checks to be disabled. A failed or offline check must not block startup or chat.
- Show the available version and release notes, with Update now and Later choices. No GitHub account should be required.

Settings > Updates (explicitly requested by Jeremy):

- Automatically check for updates in the background by default, with a setting to disable automatic checks and a manual Check for updates button.
- Display the installed version and update status.
- Reveal an Update to vX.X.X button when a newer published release is available.
- Clicking the update button obtains and verifies the updater if necessary, then launches it through BEYOND's Python backend. The browser page does not execute PowerShell directly.
- Explain the required app closure/restart before proceeding. Update checks may be automatic; installing remains user initiated.
- Launch a separate updater process that continues after BEYOND closes and can finish the update and offer restart while preserving user data.
- Restrict updater launch to authorized host/administrator access using the existing access controls; ordinary remote chat users must not be able to update the host installation.

Updater delivery:

- Proposed standalone Windows updater: Update-Beyond.ps1, optionally paired with an Update-Beyond.cmd launcher for double-click use.
- Publish the updater as a GitHub release asset so existing 1.0.0 users can download it and run it against their current installation. Later versions can initiate the process inside BEYOND.
- Console download example (proposed asset, not created or published yet):

```powershell
Invoke-WebRequest `
  -Uri "https://github.com/jeremystevens/beyond/releases/latest/download/Update-Beyond.ps1" `
  -OutFile "Update-Beyond.ps1"
```

- PowerShell can bootstrap the update even if the Python environment needs repair. Downloading the script is separate from executing it; final run instructions and PowerShell execution-policy handling need design/testing.

Proposed update workflow:

1. Locate/confirm the existing BEYOND folder and read its installed version.
2. Resolve the matching published release, download its package, verify it, and extract into a temporary staging folder.
3. Ask the user to close BEYOND before modifying the installation; do not stop unrelated applications or overwrite files while BEYOND is active.
4. Back up affected application files and any data that migrations will modify. Use an explicit application-file manifest rather than blindly overwriting the whole folder.
5. Replace application files and safely remove obsolete application-owned files. Preserve chats, settings, memories, models, attachments, optional feature assets, and other user content.
6. Update changed dependencies through the existing .venv, preserving installed optional features. Reuse verified model/engine assets and download only what is needed.
7. Apply versioned database/settings migrations, verify startup, and offer to restart. Restore the previous working installation if the update fails.

To discuss: release/package verification and trust, manifest format, release publication order, interrupted updates, disk-space checks, dependency and database rollback, custom/modified source files, unsupported upgrade paths, and ZIP installs versus Git checkouts. Rollback must account for dependencies and migrated data, not just application files.

Validation must include upgrading an actual 1.0.0 installation while preserving its conversations, configuration, models, and optional features; offline/network failure and interrupted-update recovery; and confirming that a failed update leaves a usable installation.

## Next brainstorming additions

Append new candidates with a user benefit, example, overlap check, and open questions. Record decisions here when candidates are accepted, deferred, or rejected; move approved implementation details into a dedicated phase plan.
