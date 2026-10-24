// Dev-only browser regression: npm install --no-save playwright, npx playwright install chromium
// Run: node tests/web/code-blocks.browser.cjs
const {chromium} = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const web = path.resolve(__dirname, '../../app/web');

(async () => {
  const browser = await chromium.launch({headless:true, channel:process.env.BEYOND_BROWSER_CHANNEL || 'chromium'});
  try {
    const context = await browser.newContext({acceptDownloads:true, permissions:['clipboard-read','clipboard-write']});
    const page = await context.newPage();
    const errors = [];
    let savedReply = '';
    let streamedReply = '';
    page.on('pageerror', err => errors.push(err.message));
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.pathname.startsWith('/api/')) {
        if (url.pathname === '/api/chat/stream') {
          const events = [
            {type:'token',text:streamedReply},
            {type:'message',id:3,buttons:[],stats:{tokens:20,seconds:1}},
            {type:'done'}
          ];
          return route.fulfill({contentType:'application/x-ndjson',body:events.map(x=>JSON.stringify(x)).join('\n')+'\n'});
        }
        let body = {};
        if (url.pathname === '/api/chats/1') body = {id:1,messages:[
          {id:1,role:'user',kind:'chat',content:'Show an example'},
          {id:2,role:'assistant',kind:'chat',content:savedReply,buttons:[],stats:{tokens:20,seconds:1}}
        ]};
        if (url.pathname === '/api/chats') body = [];
        if (url.pathname === '/api/commands') body = [];
        if (url.pathname === '/api/ai-status') body = {state:'ok',model:'test'};
        if (url.pathname.startsWith('/api/reminders/fired')) body = {items:[],latest:0};
        return route.fulfill({json:body});
      }
      const file = path.join(web, url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//,''));
      if (!file.startsWith(web + path.sep) || !fs.existsSync(file)) return route.fulfill({status:404,body:''});
      const type = file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html';
      return route.fulfill({body:fs.readFileSync(file),contentType:type});
    });
    await page.goto('http://localhost:7770/');
    await page.waitForFunction(() => typeof bubble === 'function');
    const python = 'class Cat:\n    def speak(self):\n        return "café"\n';
    const html = '<script>window.pwned=true</script>\n<img src=x onerror="window.pwned=true">\n';
    const reply = 'Here is Python:\n```python\n'+python+'```\nExplanation.\n```html\n'+html+'```\nDone.';
    await page.evaluate(text => {
      const el = bubble('assistant', text); el.id='test-reply';
      showStats(el,{tokens:20,seconds:1,tokens_per_second:20});
      arrangeFooter(el);
    },reply);
    assert.equal(await page.locator('#test-reply .code-block').count(),2);
    assert.ok(await page.locator('#test-reply .hljs-keyword').count());
    assert.equal(await page.evaluate(() => window.pwned),undefined);
    assert.equal(await page.locator('#test-reply pre img, #test-reply pre script').count(),0);
    await page.locator('#test-reply .code-action').nth(0).click();
    assert.equal((await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g,'\n'),python);
    const downloadPromise=page.waitForEvent('download');
    await page.locator('#test-reply .code-action').nth(3).click();
    const download=await downloadPromise;
    assert.equal(download.suggestedFilename(),'code-2.html');
    assert.equal(fs.readFileSync(await download.path(),'utf8'),html);
    assert.equal(await page.evaluate(() => answerText(document.querySelector('#test-reply'))),reply);
    await page.locator('#test-reply .foot [data-kind="copy"]').click();
    assert.equal((await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g,'\n'),reply);

    // Reopening uses the same bubble/fill path; no highlighting/control labels leak into source.
    savedReply = reply;
    await page.evaluate(() => openChat(1));
    await page.locator('.msg.assistant').first().evaluate(el => {el.id='test-reply';});
    assert.equal(await page.locator('#test-reply pre code').first().textContent(),python);
    await page.evaluate(() => {
      const el=bubble('assistant writing','```python\nclass Pa'); el.id='stream-test';
    });
    assert.equal(await page.locator('#stream-test .code-action:disabled').count(),2);
    assert.equal(await page.locator('#stream-test .hljs-keyword').count(),0);
    await page.evaluate(() => {
      const el=document.querySelector('#stream-test'); fill(el,'```python\nclass Partial:\n    pass');
      el.classList.remove('writing'); BeyondCode.complete(el);
    });
    assert.equal(await page.locator('#stream-test .code-action:disabled').count(),0);
    await page.locator('#stream-test .code-action').first().click();
    assert.equal((await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g,'\n'),'class Partial:\n    pass');

    streamedReply = '```python\nprint("streamed")\n```';
    await page.evaluate(() => streamAnswer('/api/chat/stream',{content:'Show code'},bubble('user','Show code'),()=>{}));
    assert.equal(await page.locator('.msg.assistant').last().locator('.code-action:disabled').count(),0);
    assert.ok(await page.locator('.msg.assistant').last().locator('.hljs-built_in').count());

    // Unknown language and missing highlighter retain working controls and literal code.
    await page.evaluate(() => { window.hljs=undefined; const el=bubble('assistant','```unknown\n<safe>\n```'); el.id='fallback-test'; });
    assert.equal(await page.locator('#fallback-test code').textContent(),'<safe>\n');
    await page.evaluate(() => {
      Object.defineProperty(navigator,'clipboard',{configurable:true,value:undefined});
      document.execCommand = action => { window.fallbackText=document.activeElement.value; return action==='copy'; };
    });
    await page.locator('#fallback-test .code-action').first().click();
    assert.equal(await page.evaluate(() => window.fallbackText),'<safe>\n');
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(() => {
      const el=bubble('assistant','```python\n'+ 'x'.repeat(400)+'\n```'); el.id='wide-test';
      el.scrollIntoView();
    });
    const sizing=await page.locator('#wide-test').evaluate(el => ({
      body:document.body.scrollWidth,viewport:innerWidth,right:el.getBoundingClientRect().right,
      pre:el.querySelector('pre').scrollWidth,client:el.querySelector('pre').clientWidth
    }));
    assert.ok(sizing.body<=sizing.viewport && sizing.right<=sizing.viewport,JSON.stringify(sizing));
    assert.ok(sizing.pre>sizing.client);
    await page.screenshot({path:process.env.BEYOND_SCREENSHOT || 'code-blocks-mobile.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('PASS: real chat page, highlighting, exact copy/download, whole reply, reopen, partial streams, HTML safety, fallback, mobile overflow');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode=1;});
