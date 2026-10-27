/* Hands-free voice turns use existing transcription, chat and speech APIs. */
window.BeyondVoiceConversation = (() => {
  function init(adapter) {
    const $ = id => document.getElementById(id);
    const setup = $('voice-conversation-setup'), result = $('voice-conversation-export');
    const bar = $('voice-session'), label = $('voice-session-status'), pauseButton = $('voice-session-pause');
    const owned = new Set();
    let active = false, paused = false, generation = 0, keepTranscript = false, transcript = [];
    let stream = null, recorder = null, context = null, sampleTimer = null, request = null, player = null;
    let pendingSpeech = null, lastTranscript = '', setupSerial = 0, starting = false;
    const valid = n => active && !paused && generation === n;
    const status = text => { label.textContent = text; };
    function stopCapture() {
      clearInterval(sampleTimer); sampleTimer = null;
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
      paused = true; generation++; stopCapture(); abortRequest(); adapter.stopOwned();
      if (player) player.pause();
      pauseButton.textContent = 'Resume'; status(reason);
    }
    function end(offer = true) {
      if (!active) return;
      active = false; paused = false; generation++; stopCapture(); abortRequest(); adapter.stopOwned();
      if (player) { player.pause(); player.removeAttribute('src'); player = null; }
      pendingSpeech = null; bar.hidden = true; pauseButton.textContent = 'Pause';
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
          player = null; pendingSpeech = null;
          if (active && !paused) listen(generation);
        }, {once:true});
        clip.addEventListener('error', () => { if (player !== clip) return; player = null; if (active && !paused) pause('Could not play the spoken reply. Check audio and try Resume.'); }, {once:true});
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
        let recordedReply = false;
        const reply = await adapter.send(text, (id, answer) => {
          owned.add(id); if (owned.size > 500) owned.delete(owned.values().next().value);
          if (valid(n) && answer) { recordedReply = addTranscript('BEYOND', answer); pendingSpeech = id; }
        });
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
          analyser.getByteTimeDomainData(samples);
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
      paused = false; pauseButton.textContent = 'Pause'; const n = ++generation;
      if (player) {
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
      active = true; paused = false; const n = ++generation;
      setup.close(); bar.hidden = false; pauseButton.textContent = 'Pause'; adapter.onActive(true); listen(n);
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
