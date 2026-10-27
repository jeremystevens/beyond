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
