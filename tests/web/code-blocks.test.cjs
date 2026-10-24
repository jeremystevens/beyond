const { test } = require('node:test');
const assert = require('node:assert/strict');
const code = require('../../app/web/code-blocks.js');

test('multiple blocks preserve exact source, indentation, Unicode, and prose boundaries', () => {
  const parts = code.split('Example:\n```python\nclass Cat:\n\tname = "café"\n\n```\nThen:\n~~~json\n{"ok": true}\n~~~\nDone.');
  assert.deepEqual(parts, [
    {type:'text',text:'Example:\n'},
    {type:'code',code:'class Cat:\n\tname = "café"\n\n',language:'python',closed:true},
    {type:'text',text:'Then:\n'},
    {type:'code',code:'{"ok": true}\n',language:'json',closed:true},
    {type:'text',text:'Done.'}
  ]);
});

test('CRLF and no terminal newline are preserved, including stopped streams', () => {
  assert.equal(code.split('```py\r\nx = 1\r\n```')[0].code, 'x = 1\r\n');
  assert.deepEqual(code.split('```python\n  partial'), [{type:'code',code:'  partial',language:'python',closed:false}]);
  assert.deepEqual(code.split('```py'), [{type:'text',text:'```py'}]);
});

test('nested fences require the matching character and sufficient length', () => {
  assert.equal(code.split('````markdown\n```py\nx=1\n```\n~~~\n````')[0].code, '```py\nx=1\n```\n~~~\n');
  assert.equal(code.split('Inline `code` stays text')[0].type,'text');
  assert.equal(code.split('```python\n```not-a-close\n```')[0].code,'```not-a-close\n');
});

test('suggested names use controlled extensions and cannot contain source-provided paths', () => {
  assert.equal(code.filename('python',1),'code-1.py');
  assert.equal(code.filename('powershell',2),'code-2.ps1');
  assert.equal(code.filename('../../evil.exe',3),'code-3.txt');
  assert.equal(code.filename('__proto__',4),'code-4.txt');
});
