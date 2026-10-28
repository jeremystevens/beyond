/* Hands-free voice turns use existing transcription, chat and speech APIs. */
window.BeyondVoiceConversation = (() => {
  function init(adapter) {
    const $ = id => document.getElementById(id);
    const setup = $('voice-conversation-setup'), result = $('voice-conversation-export');
    const bar = $('voice-session'), label = $('voice-session-status'), pauseButton = $('voice-session-pause');
    const wave = $('voice-waveform');
    let visualContext = null, visualTimer = null;
    function drawWave(samples) {
      if (!wave) return;
      const bars = Array.from(wave.children);
      bars.forEach((bar, i) => {
        let sum = 0;
        const start = Math.floor(i * samples.length / bars.length);
        const end = Math.floor((i + 1) * samples.length / bars.length);
        for (let j = start; j < end; j++) sum += Math.pow((samples[j] - 128) / 128, 2);
        bar.style.height = Math.min(32, 3 + Math.sqrt(sum / Math.max(1, end - start)) * 100) + 'px';
      });
    }
    function stopVisual() {
      clearInterval(visualTimer); visualTimer = null;
      if (visualContext) { visualContext.close().catch(() => {}); visualContext = null; }
      if (wave) Array.from(wave.children).forEach(bar => { bar.style.height = '3px'; });
    }
    async function playbackVisual(clip) {
      stopVisual();
      try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        const ctx = new Ctx(); visualContext = ctx;
        const analyser = ctx.createAnalyser(); analyser.fftSize = 512;
        const source = ctx.createMediaElementSource(clip);
        source.connect(analyser); analyser.connect(ctx.destination);
        ctx.resume().catch(() => {});
        if (visualContext !== ctx) return;
        const samples = new Uint8Array(analyser.fftSize);
        visualTimer = setInterval(() => {
          if (clip.paused) { if (wave) Array.from(wave.children).forEach(bar => { bar.style.height = '3px'; }); return; }
          analyser.getByteTimeDomainData(samples); drawWave(samples);
        }, 80);
      } catch { stopVisual(); }
    }
    let endingConfirmation = false, endAfterPlayback = false, unclearConfirmations = 0;
    let wakeLock = null, wakeSerial = 0;
    function releaseWake() {
      wakeSerial++;
      const lock = wakeLock; wakeLock = null;
      if (lock) lock.release().catch(() => {});
    }
    async function acquireWake() {
      if (!navigator.wakeLock || document.hidden || !active || paused) return;
      const serial = ++wakeSerial;
      try {
        const lock = await navigator.wakeLock.request('screen');
        if (serial !== wakeSerial || !active || paused || document.hidden) { await lock.release(); return; }
        wakeLock = lock;
        lock.addEventListener('release', () => { if (wakeLock === lock) wakeLock = null; });
      } catch { /* The OS can decline; normal voice controls remain available. */ }
    }
    const owned = new Set();
    let active = false, paused = false, generation = 0, keepTranscript = false, transcript = [];
    let stream = null, recorder = null, context = null, sampleTimer = null, request = null, player = null;
    let pendingSpeech = null, lastTranscript = '', setupSerial = 0, starting = false;
    const valid = n => active && !paused && generation === n;
    const status = text => { label.textContent = text; bar.dataset.state = /^Listening/.test(text) ? 'listening' : /^Speaking/.test(text) ? 'speaking' : /^(Thinking|Transcribing|Preparing)/.test(text) ? 'working' : 'paused'; };
    function stopCapture() {
      clearInterval(sampleTimer); sampleTimer = null;
      if (wave) Array.from(wave.children).forEach(bar => { bar.style.height = '3px'; });
      if (recorder) {
        recorder.ondataavailable = null; recorder.onstop = null; recorder.onerror = null;
        try { if (recorder.state !== 'inactive') recorder.stop(); } catch {}
        recorder = null;
      }
      if (stream) { stream.getTracks().forEach(track => track.stop()); stream = null; }
      if (context) { context.close().catch(() => {}); context = null; }
    }
    function abortRequest() { if (request) request.abort(); request = null; }
    function addTranscript(role, text) {
      if (!keepTranscript) return true;
      if (transcript.length >= 400 || transcript.reduce((n, item) => n + item.text.length, 0) + text.length > 500000) {
        pause('Transcript is full. End and save it before starting another session.'); return false;
      }
      transcript.push({role, text}); return true;
    }
    function pause(reason = 'Paused') {
      if (!active || paused) return;
      releaseWake(); paused = true; generation++; stopCapture(); abortRequest(); adapter.stopOwned();
      if (player) player.pause();
      pauseButton.textContent = 'Resume'; status(reason);
    }
    function end(offer = true) {
      if (!active) return;
      releaseWake(); active = false; paused = false; generation++; stopCapture(); abortRequest(); adapter.stopOwned();
      if (player) { player.pause(); player.removeAttribute('src'); player = null; }
      stopVisual(); pendingSpeech = null; bar.hidden = true; pauseButton.textContent = 'Pause';
      adapter.onActive(false);
      if (keepTranscript && transcript.length && offer) {
        lastTranscript = 'BEYOND voice conversation\n\n' + transcript.map(item => item.role + ': ' + item.text).join('\n\n') + '\n';
        $('voice-export-summary').textContent = transcript.length + ' recorded messages. Save them to a text file?';
        result.showModal();
      }
      transcript = []; keepTranscript = false;
    }
    async function fetchJson(url, options = {}) {
      const controller = new AbortController(); request = controller;
      try {
        const response = await fetch(url, {...options, signal:controller.signal});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'The voice request failed.');
        return data;
      } finally { if (request === controller) request = null; }
    }
    function fail(error, n) {
      if (!valid(n) || error?.name === 'AbortError') return;
      pause(error?.message || 'Voice conversation stopped. Check the microphone and voice settings.');
    }
    async function speak(id, n) {
      try {
        status('Preparing spoken reply…');
        let info = await fetchJson('/api/speech', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message_id:id})});
        const start = Date.now();
        while (valid(n) && info.state === 'pending') {
          if (Date.now() - start > 180000) throw new Error('Spoken reply took too long. Pause or end, then try again.');
          await new Promise(resolve => setTimeout(resolve, 1200));
          if (!valid(n)) return;
          const data = await fetchJson('/api/speech/status?chat_id=' + adapter.getChatId());
          info = data.items.find(item => item.id === id) || {state:'error', error:'The spoken reply is no longer available.'};
        }
        if (!valid(n)) return;
        if (info.state !== 'ready' || !info.url) throw new Error(info.error || 'Spoken reply is not available. Check Spoken replies in Settings.');
        adapter.stopOtherAudio();
        const clip = new Audio(info.url); player = clip;
        clip.addEventListener('ended', () => {
          if (player !== clip) return;
          stopVisual(); player = null; pendingSpeech = null;
          if (active && endAfterPlayback) { endAfterPlayback = false; end(); return; }
          if (active && !paused) listen(generation);
        }, {once:true});
        clip.addEventListener('error', () => { if (player !== clip) return; player = null; if (active && !paused) pause('Could not play the spoken reply. Check audio and try Resume.'); }, {once:true});
        await playbackVisual(clip);
        status(info.truncated ? 'Speaking… (reply shortened for audio)' : 'Speaking…');
        try { await clip.play(); } catch {
          if (valid(n) && player === clip) pause('Tap Resume to play the spoken reply.');
        }
      } catch (error) { fail(error, n); }
    }
    async function handleAudio(blob, type, n) {
      try {
        status('Transcribing…');
        const data = await fetchJson('/api/transcribe', {method:'POST', headers:{'Content-Type':type}, body:blob});
        if (!valid(n)) return;
        const text = (data.text || '').trim();
        if (!text) { listen(n); return; }
        if (!addTranscript('You', text)) return;
        status('Thinking…');
        let outgoing = text;
        const words = text.toLowerCase().replace(/[’‘]/g, "'").replace(/[^a-z0-9\s']/g, '').replace(/\s+/g, ' ').trim();
        const naturalEnd = /^(?:goodbye\s+)?(?:it is time to|it's time to|lets(?: go ahead and)?|let's(?: go ahead and)?|i want to|i would like to|i'd like to|i am about to|i'm about to|we can) (?:end|stop|finish) (?:the|this|our) (?:call|voice call|voice chat|conversation)(?: now)?(?: goodbye| bye| thank you| thanks| please)?$/.test(words);
        const requestedEnd = /^(?:hang up\s*)+(?:please\s*(?:hang up)?)?$/.test(words) || /^(?:(?:please|can you|could you) )?(?:hang up(?: the call)?|stop (?:the )?voice chat|(?:lets|let's) finish (?:our|the|this) conversation)(?: now| please| thank you)?$/.test(words) || naturalEnd || /^(?:(?:please|can you|could you|would you)\s+)?(?:end|stop|hang up|disconnect)(?:\s+(?:the|this|our))?\s*(?:call|voice call|voice chat|conversation)?(?:\s+(?:now|please|thank you))?$/.test(words)
          || /^(?:i want to|i would like to|i'd like to|i am about to|i'm about to) end (?:the|this|our) (?:call|conversation)$/.test(words);
        if (endingConfirmation) {
          const declined = /\b(?:no|nope|cancel|not yet|keep talking|dont|don't|do not)\b/.test(words);
          const accepted = !declined && (/^(?:yes|yeah|yep|yup|sure|okay|ok|confirm|absolutely|please do|go ahead)\b/.test(words) || requestedEnd);
          if (accepted) {
            endingConfirmation = false; endAfterPlayback = true;
            outgoing = '/speak Goodbye. Thanks for talking with me.';
          } else if (declined) {
            endingConfirmation = false;
            outgoing = '/speak Okay, we can keep talking.';
          } else {
            unclearConfirmations++;
            if (unclearConfirmations >= 2) {
              endingConfirmation = false;
              pause('Could not confirm ending the call. Tap End to finish, or Resume to continue.');
              return;
            }
            outgoing = '/speak Would you like me to end our conversation? Please say yes or no.';
          }
        } else if (requestedEnd) {
          endingConfirmation = true; unclearConfirmations = 0;
          outgoing = '/speak Would you like me to end our conversation?';
        }
        let recordedReply = false;
        const reply = await adapter.send(outgoing, (id, answer) => {
          owned.add(id); if (owned.size > 500) owned.delete(owned.values().next().value);
          if (valid(n) && answer) { recordedReply = addTranscript('BEYOND', answer); pendingSpeech = id; }
        }, text);
        if (!valid(n)) return;
        if (!reply || !reply.id || !reply.text) throw new Error('The reply did not finish. Resume to try another message.');
        if (!recordedReply && !addTranscript('BEYOND', reply.text)) return;
        pendingSpeech = reply.id;
        await speak(reply.id, n);
      } catch (error) {
        if (valid(n) && /didn.t catch any words/i.test(error?.message || '')) { listen(n); return; }
        fail(error, n);
      }
    }
    async function listen(n) {
      if (!valid(n)) return;
      if (adapter.isBusy()) { pause('Chat is busy. Resume when the current reply finishes.'); return; }
      status('Listening…');
      try {
        const acquired = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
        if (!valid(n)) { acquired.getTracks().forEach(track => track.stop()); return; }
        stream = acquired;
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) throw new Error('This browser cannot detect speech pauses. Try a current Chrome, Edge or Firefox.');
        const localContext = new AudioCtx(); context = localContext;
        if (localContext.state === 'suspended') await localContext.resume();
        if (!valid(n)) { acquired.getTracks().forEach(track => track.stop()); localContext.close().catch(() => {}); return; }
        const analyser = context.createAnalyser(); analyser.fftSize = 512;
        context.createMediaStreamSource(stream).connect(analyser);
        const samples = new Uint8Array(analyser.fftSize);
        const chunks = []; let speakingFrames = 0, heard = false, lastSpeech = 0;
        const began = Date.now();
        recorder = new MediaRecorder(stream);
        recorder.onerror = () => { if (valid(n)) pause('Recording stopped unexpectedly. Check the microphone and resume.'); };
        recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
        recorder.onstop = () => {
          const type = (recorder?.mimeType || 'audio/webm').split(';')[0];
          recorder = null; stopCapture();
          if (!valid(n)) return;
          if (heard && chunks.length) handleAudio(new Blob(chunks, {type}), type, n);
          else listen(n);
        };
        recorder.start();
        sampleTimer = setInterval(() => {
          if (!valid(n) || !recorder || recorder.state === 'inactive') return;
          analyser.getByteTimeDomainData(samples); drawWave(samples);
          let sum = 0; for (const sample of samples) { const value = (sample - 128) / 128; sum += value * value; }
          const now = Date.now(), loud = Math.sqrt(sum / samples.length) > 0.025;
          speakingFrames = loud ? speakingFrames + 1 : 0;
          if (speakingFrames >= 3) heard = true;
          if (heard && loud) lastSpeech = now;
          if ((heard && now - lastSpeech >= 1200) || now - began >= 30000) recorder.stop();
        }, 100);
      } catch (error) {
        if (!valid(n)) return;
        stopCapture();
        if (error?.name === 'NotAllowedError') error = new Error('Microphone permission was denied. Allow it in your browser and resume.');
        else if (error?.name === 'NotFoundError') error = new Error('No microphone was found. Connect one and resume.');
        fail(error, n);
      }
    }
    async function resume() {
      if (!active || !paused) return;
      if (adapter.isBusy()) { status('Chat is busy. Resume when the current reply finishes.'); return; }
      paused = false; acquireWake(); pauseButton.textContent = 'Pause'; const n = ++generation;
      if (player) {
        if (visualContext) visualContext.resume().catch(() => {});
        status('Speaking…');
        try { await player.play(); } catch { if (valid(n)) pause('Tap Resume to play the spoken reply.'); }
      } else if (pendingSpeech) speak(pendingSpeech, n);
      else listen(n);
    }
    $('voice-conversation-open').onclick = () => {
      if (active) { bar.scrollIntoView({block:'nearest'}); return; }
      setupSerial++; $('voice-setup-error').textContent = '';
      $('voice-save-transcript').checked = false;
      setup.showModal();
    };
    $('voice-setup-close').onclick = () => setup.close();
    setup.addEventListener('close', () => { setupSerial++; if (!active) abortRequest(); });
    $('voice-setup-start').onclick = async () => {
      if (starting) return;
      if (adapter.isBusy()) { $('voice-setup-error').textContent = 'Wait for the current chat or recording to finish.'; return; }
      if (!window.isSecureContext) {
        $('voice-setup-error').textContent = 'On another device, open the secure HTTPS address shown under Settings → Address and network to use the microphone.'; return;
      }
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !(window.AudioContext || window.webkitAudioContext)) {
        $('voice-setup-error').textContent = 'This browser cannot record voice. Try a current Chrome, Edge or Firefox.'; return;
      }
      const serial = setupSerial; starting = true; $('voice-setup-start').disabled = true;
      try {
        const data = await fetchJson('/api/settings');
        if (!data.values?.speech_enabled) throw new Error('Turn on Spoken replies in Settings first.');
      } catch (error) { if (setup.open && serial === setupSerial) $('voice-setup-error').textContent = error.message || 'Could not check voice settings.'; return; }
      finally { starting = false; $('voice-setup-start').disabled = false; }
      if (!setup.open || serial !== setupSerial || adapter.isBusy()) return;
      keepTranscript = $('voice-save-transcript').checked; transcript = []; pendingSpeech = null;
      endingConfirmation = false; endAfterPlayback = false;
      active = true; paused = false; const n = ++generation;
      setup.close(); bar.hidden = false; pauseButton.textContent = 'Pause'; adapter.onActive(true); acquireWake(); listen(n);
    };
    pauseButton.onclick = () => paused ? resume() : pause();
    $('voice-session-end').onclick = () => end();
    $('voice-export-save').onclick = () => {
      const url = URL.createObjectURL(new Blob([lastTranscript], {type:'text/plain;charset=utf-8'}));
      const link = document.createElement('a'); link.href = url; link.download = 'beyond-voice-transcript.txt';
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000);
      lastTranscript = ''; result.close();
    };
    $('voice-export-close').onclick = () => { lastTranscript = ''; result.close(); };
    result.addEventListener('cancel', event => event.preventDefault());
    result.addEventListener('close', () => { lastTranscript = ''; });
    document.addEventListener('visibilitychange', () => { if (document.hidden) pause('Paused while this tab is in the background.'); });
    window.addEventListener('pagehide', () => end(false));
    return {pause, end, isActive:() => active, owns:id => owned.has(id)};
  }
  return {init};
})();
