/* Guided writing uses one model request; drafts stay in this dialog until copied or downloaded. */
window.BeyondWriting = (() => {
  function init({ getChatId, hasAttachments, isBusy }) {
    const $ = id => document.getElementById('writing-' + id);
    const dialog = $('dialog');
    let loaded = false, controller = null, serial = 0, lastChat = undefined;
    function status(text, error = false) {
      $('status').textContent = text;
      $('status').classList.toggle('writing-error', error);
    }
    function taskChanged() {
      const task = $('task').value;
      $('source-label').textContent = task === 'email' ? 'Email you received' : task === 'document' ? 'Source notes or specifications (optional)' : 'Text to polish';
      $('instructions-label').textContent = task === 'email' ? 'What should your reply say?' : task === 'document' ? 'What document should BEYOND write?' : 'Anything to change or keep? (optional)';
      $('source').required = task !== 'document';
      $('instructions').required = task === 'email';
      $('format-field').hidden = task !== 'document';
    }
    function busy(on) {
      dialog.setAttribute('aria-busy', String(on));
      for (const id of ['generate', 'revise', 'task', 'tone', 'source', 'instructions', 'audience', 'detail', 'format', 'attachments', 'revision', 'draft']) $(id).disabled = on;
      if (!on) $('attachments').disabled = !hasAttachments();
      $('cancel').hidden = !on;
    }
    async function loadOptions() {
      if (loaded) return;
      const response = await fetch('/api/writing/options');
      if (!response.ok) throw new Error('The Writing helper is unavailable. Refresh the page after updating and restarting BEYOND.');
      const data = await response.json();
      for (const [field, key] of [['task', 'tasks'], ['tone', 'tones'], ['format', 'formats'], ['detail', 'details']]) {
        $(field).replaceChildren();
        for (const item of data[key]) {
          const option = document.createElement('option'); option.value = item.id; option.textContent = item.label;
          if (item.description) option.title = item.description;
          $(field).append(option);
        }
      }
      $('task').value = 'rewrite'; $('tone').value = 'professional'; $('detail').value = 'standard';
      $('source').maxLength = data.max_text; $('draft').maxLength = data.max_draft;
      $('instructions').maxLength = $('revision').maxLength = data.max_directions;
      loaded = true; taskChanged();
    }
    async function open() {
      if (isBusy()) { document.getElementById('input').focus(); return; }
      if (dialog.open) return;
      if (getChatId() !== lastChat) $('attachments').checked = false;
      lastChat = getChatId();
      dialog.showModal();
      status('Choose a task and tone. Your draft is not sent as an email or saved to chat.');
      $('generate').disabled = true;
      try {
        await loadOptions();
        $('attachments').disabled = !hasAttachments();
        if (!hasAttachments()) $('attachments').checked = false;
        $('generate').disabled = false;
        $('source').focus();
      } catch (error) { status(error.message, true); }
    }
    function cancel() {
      serial++;
      controller?.abort(); controller = null;
      busy(false);
      status('Generation cancelled. Your text and previous draft are unchanged.');
    }
    async function generate(revising = false) {
      if (controller || !$('form').reportValidity()) return;
      if (revising && (!$('draft').value.trim() || !$('revision').value.trim())) {
        status('Enter what you want to change in the draft.', true); $('revision').focus(); return;
      }
      const request = {
        task: $('task').value, tone: $('tone').value, source: $('source').value,
        instructions: $('instructions').value, audience: $('audience').value, detail: $('detail').value,
        document_format: $('format').value, previous: revising ? $('draft').value : '',
        revision: revising ? $('revision').value : '', use_attachments: $('attachments').checked,
        chat_id: $('attachments').checked ? getChatId() : null
      };
      const mine = ++serial;
      controller = new AbortController(); busy(true);
      status(revising ? 'Revising your draft…' : 'Writing your draft… This can take a moment.');
      try {
        const response = await fetch('/api/writing/draft', {method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify(request), signal:controller.signal});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || (response.status === 404 ? 'Restart BEYOND after updating to use the Writing helper.' : 'The draft could not be created. Your text is unchanged.'));
        if (mine !== serial) return;
        $('draft').value = data.draft;
        $('result').hidden = false; $('revision').value = '';
        $('draft').dataset.filename = request.task === 'document' && request.document_format === 'readme' ? 'README.md' : request.task === 'email' ? 'email-reply.txt' : 'document.txt';
        status('Draft ready. Review the facts and edit it before using it.');
      } catch (error) {
        if (mine === serial) status(error.name === 'AbortError' ? 'Cancelled. Your text is unchanged.' :
          error.name === 'TypeError' ? 'BEYOND is not responding. Your text and previous draft are unchanged.' : error.message, true);
      } finally {
        if (mine === serial) {controller = null; busy(false);}
      }
    }
    $('task').onchange = taskChanged;
    $('form').onsubmit = event => {event.preventDefault(); generate();};
    $('revise').onclick = () => generate(true);
    $('cancel').onclick = cancel;
    $('close').onclick = () => dialog.close();
    dialog.addEventListener('close', () => { if (controller) cancel(); document.getElementById('input').focus(); });
    $('copy').onclick = async () => {
      const text = $('draft').value;
      try {
        try {
          if (!navigator.clipboard || !window.isSecureContext) throw new Error('Use selection');
          await navigator.clipboard.writeText(text);
        } catch {
          $('draft').focus(); $('draft').select();
          if (!document.execCommand('copy')) throw new Error('Clipboard unavailable');
        }
        status('Draft copied.');
      } catch {status('Copy is unavailable. Select the draft and copy it manually.', true);}
    };
    $('save').onclick = () => {
      const url = URL.createObjectURL(new Blob([$('draft').value], {type:'text/plain;charset=utf-8'}));
      const link = document.createElement('a'); link.href = url; link.download = $('draft').dataset.filename || 'document.txt';
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 30000);
    };
    document.getElementById('writing-open').onclick = open;
    return {open};
  }
  return {init};
})();
