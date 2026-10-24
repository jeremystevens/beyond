/* Fenced code only; all other message text remains plain text. No model HTML is executed. */
(function (root) {
  'use strict';
  const sources = new WeakMap();
  const rawCode = new WeakMap();
  const extensions = Object.freeze({
    python: 'py', py: 'py', python3: 'py', javascript: 'js', js: 'js', jsx: 'jsx',
    typescript: 'ts', ts: 'ts', tsx: 'tsx', bash: 'sh', shell: 'sh', sh: 'sh',
    powershell: 'ps1', ps1: 'ps1', ps: 'ps1', c: 'c', cpp: 'cpp', 'c++': 'cpp',
    csharp: 'cs', cs: 'cs', 'c#': 'cs', java: 'java', json: 'json', yaml: 'yaml', yml: 'yml',
    html: 'html', xml: 'xml', css: 'css', sql: 'sql', markdown: 'md', md: 'md',
    rust: 'rs', rs: 'rs', go: 'go', golang: 'go', php: 'php', ruby: 'rb', rb: 'rb',
    swift: 'swift', kotlin: 'kt', kt: 'kt', ini: 'ini', toml: 'toml',
    plaintext: 'txt', text: 'txt', txt: 'txt', batch: 'bat', bat: 'bat', dos: 'bat'
  });

  function language(info) {
    return (info.trim().split(/\s+/)[0] || '').toLowerCase().replace(/^language-/, '').slice(0, 40);
  }

  function filename(lang, index) {
    const ext = Object.hasOwn(extensions, lang) ? extensions[lang] : 'txt';
    return 'code-' + index + '.' + ext;
  }

  // Preserve source bytes, including CRLF, indentation, blank lines, and final newlines.
  // Only fence lines are removed. A partial fence stays text until its opening line is complete.
  function split(text) {
    const result = [];
    const lines = text.match(/[^\r\n]*(?:\r\n|\n|\r|$)/g) || [];
    let prose = '', code = '', fence = null;
    for (const line of lines) {
      if (!line) continue;
      const body = line.replace(/(?:\r\n|\n|\r)$/, '');
      if (fence) {
        const closing = /^ {0,3}(`+|~+)[ \t]*$/.exec(body);
        if (closing && closing[1][0] === fence.mark && closing[1].length >= fence.size) {
          result.push({ type: 'code', code, language: fence.language, closed: true });
          code = ''; fence = null;
        } else code += line;
      } else {
        const opening = /^ {0,3}(`{3,}|~{3,})([^\r\n]*)$/.exec(body);
        if (opening && /[\r\n]$/.test(line) && !(opening[1][0] === '`' && opening[2].includes('`'))) {
          if (prose) result.push({ type: 'text', text: prose });
          prose = '';
          fence = { mark: opening[1][0], size: opening[1].length, language: language(opening[2]) };
        } else prose += line;
      }
    }
    if (fence) result.push({ type: 'code', code, language: fence.language, closed: false });
    if (prose) result.push({ type: 'text', text: prose });
    return result;
  }

  function appendText(el, text) {
    let last = 0;
    for (const m of text.matchAll(/https?:\/\/[^\s<>"'“”‘’«»]+/g)) {
      const url = m[0].replace(/[.,;:!?)\]}]+$/, '');
      el.append(text.slice(last, m.index));
      const a = document.createElement('a');
      a.href = url; a.textContent = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
      el.append(a);
      last = m.index + url.length;
    }
    el.append(text.slice(last));
  }

  async function copyText(text) {
    if (navigator.clipboard && root.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return; } catch { /* HTTP/permission fallback below */ }
    }
    const previous = document.activeElement;
    const selection = document.getSelection();
    const ranges = selection ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i).cloneRange()) : [];
    const area = document.createElement('textarea');
    area.value = text; area.style.cssText = 'position:fixed;opacity:0;left:0;top:0';
    document.body.append(area);
    try {
      area.focus(); area.select();
      if (!document.execCommand('copy')) throw new Error('Clipboard unavailable');
    } finally {
      area.remove(); previous?.focus({ preventScroll: true });
      if (selection) { selection.removeAllRanges(); ranges.forEach(range => selection.addRange(range)); }
    }
  }

  function highlight(codeEl, lang) {
    const code = rawCode.get(codeEl);
    // Bound highlighting cost; unknown languages and large blocks remain usable plain code.
    if (!root.hljs || !lang || code.length > 100000 || !root.hljs.getLanguage(lang)) return;
    try {
      // Only the pinned highlighter's escaped output enters innerHTML, never reply text.
      codeEl.innerHTML = root.hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
    } catch { codeEl.textContent = code; }
  }

  function render(el, text, options = {}) {
    sources.set(el, text);
    el.textContent = '';
    let index = 0;
    for (const part of split(text)) {
      if (part.type === 'text') { appendText(el, part.text); continue; }
      index++;
      const block = document.createElement('section'); block.className = 'code-block';
      const bar = document.createElement('div'); bar.className = 'code-toolbar';
      const label = document.createElement('span'); label.className = 'code-language';
      label.textContent = part.language || 'code';
      const status = document.createElement('span'); status.className = 'code-status';
      status.setAttribute('role', 'status');
      const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'code-action';
      copy.textContent = 'Copy code'; copy.title = 'Copy only this code block';
      const save = document.createElement('button'); save.type = 'button'; save.className = 'code-action';
      save.textContent = 'Save code'; save.title = 'Download only this code block';
      copy.disabled = save.disabled = !!options.streaming;
      const name = filename(part.language, index);
      copy.setAttribute('aria-label', 'Copy code block ' + index);
      save.setAttribute('aria-label', 'Save code block ' + index);
      copy.onclick = async () => {
        try {
          await copyText(part.code); status.textContent = 'Copied';
          setTimeout(() => { status.textContent = ''; }, 2000);
        } catch { status.textContent = 'Copy failed. Select the code to copy it.'; }
      };
      save.onclick = () => {
        const url = URL.createObjectURL(new Blob([part.code], { type: 'text/plain;charset=utf-8' }));
        const link = document.createElement('a'); link.href = url; link.download = name;
        document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 30000);
      };
      bar.append(label, status, copy, save);
      const pre = document.createElement('pre'); pre.tabIndex = 0;
      const code = document.createElement('code'); code.textContent = part.code;
      code.dataset.language = part.language; rawCode.set(code, part.code);
      if (!options.streaming) highlight(code, part.language);
      pre.append(code); block.append(bar, pre); el.append(block);
    }
  }

  function complete(el) {
    el.querySelectorAll('.code-block pre code').forEach(code => highlight(code, code.dataset.language));
    el.querySelectorAll('.code-action').forEach(button => { button.disabled = false; });
  }

  const api = { split, filename, render, complete, source: el => sources.get(el) };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.BeyondCode = api;
})(typeof window !== 'undefined' ? window : globalThis);
