# Voice conversation mode

Status: implemented for testing; unreleased after 1.2.0.

## How it works

Choose **Voice conversation** in the composer’s + menu. A small setup panel offers **Save transcript**, off by default, and **Start voice conversation**. The existing microphone continues to record a single message.

During a session a compact bar above the composer shows **Listening**, **Thinking** or **Speaking**, with Pause/Resume and End controls. BEYOND listens for speech and a pause, transcribes the user with Whisper, sends the resulting text through the normal chat, and speaks the reply using the selected Kokoro or Piper voice. It does not listen while the reply plays. Pausing or ending stops the active microphone; ending cancels work owned by the voice session where possible. A session belongs to the current browser tab and conversation.

When transcript saving is enabled, the session collects the actual recognized user text and actual BEYOND reply text. On End, offer to save the transcript as a text file. Transcript retention/export is optional; Whisper is always used for speech input. Ending without saving does not export a file. The unsaved transcript is held only in the browser tab. Ordinary chat storage and existing privacy settings continue to apply.

## Practical behavior

Use the browser’s microphone permission and existing secure-origin requirements. Clearly explain if voice input, spoken replies, microphone permission, or a supported browser is unavailable. Keep one voice turn active at a time; prevent the assistant from hearing its own playback. Silence, empty transcriptions, errors, interruption, navigation, and mobile backgrounding must leave controls usable and release the microphone. Each recording is capped at 30 seconds with silence detection; a speech preparation job already running may finish after the session ends. Do not add another model or change ordinary chat behavior.

## Validation

Test setup and opt-in transcript, microphone lifecycle, turn detection, state changes, pause/resume/end and cancellation, self-playback avoidance, text export, failed requests, and desktop/mobile layouts. Use simulated audio and mocked services for automated coverage; verify real microphone, Whisper and speech playback with the user before merging. Update README, user guide and changelog. Keep release VERSION unchanged.

## Implementation and limits

The browser uses existing /api/transcribe, /api/chat/stream and /api/speech endpoints. It captures no audio while the AI is processing or playback is active, and suppresses duplicate auto-read playback. Short speech, long pauses and background noise may affect detection; real microphone testing is needed. The tab auto-pauses when hidden. The transcript is bounded, includes the actual reply text even if audio is shortened, and is offered on End. Browser autoplay failures pause and ask the user to Resume.

## Revised direction after hands-on testing (not yet implemented)

Present a dedicated, uncluttered voice-call view with listening, thinking and speaking states plus Pause and End. Transcribe speech in the background, send it to the AI without displaying conversation bubbles, and play replies aloud. Keep the current session context available across turns. Offer an optional transcript download when the call ends, with clear explanation of whether any conversation data is retained. Keep the existing chat interface and one-message microphone unchanged.

Investigate intermittent Kokoro failures that cause Piper fallback; report a useful error without exposing private speech text. Test both speech engines under realistic memory pressure and verify the full call with an actual microphone, including silence detection, background noise, playback, pause and transcript export. Hiding text does not remove the need for transcription or AI generation and should not be presented as a substantial resource saving.

## Spoken end confirmation

Explicit spoken requests such as “End the call” ask for a yes/no confirmation. Confirmation plays a brief goodbye and ends after playback; declining returns to conversation. Ambiguous replies repeat the confirmation. The End button remains immediate.

## Mobile screen and hang-up phrases

Request a screen wake lock during an active foreground voice call, releasing it on Pause or End and requesting it again on Resume. Unsupported browsers or OS refusal must not block the call. Deliberate locking or switching apps still pauses the microphone. Explicit hang-up phrases include “Hang up”, “Stop voice chat”, “End the call”, and “Let’s finish our conversation”; each requires confirmation before ending.

## First-version scope accepted after mobile testing

The user accepted the current call UI, waveform, transcript export, and spoken confirmation as sufficient for a first version. Stop further transcription and reply tuning for this release. Document imperfect recognition and replies and the End-button fallback; track improvements for later versions. Voice turns currently still use normal saved chat storage behind the call view; separate ephemeral conversation handling is not implemented. Release and merge remain separate actions.
