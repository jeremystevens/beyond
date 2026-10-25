// Isolated real-page UI regression. The model/API replies are stand-ins; no user data or live AI is used.
const {chromium}=require('playwright');
const fs=require('node:fs'), path=require('node:path'), os=require('node:os'), assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
const labels=['Professional','Casual','Friendly','Technical and precise','Plain language','Formal','Diplomatic',
  'Firm and assertive','Warm and empathetic','Persuasive','Instructional','Academic','Concise and direct','Funny','Polite','Dramatic'];
const keys=['professional','casual','friendly','technical','plain','formal','diplomatic','assertive','empathetic',
  'persuasive','instructional','academic','concise','funny','polite','dramatic'];
const options={tones:keys.map((id,i)=>({id,label:labels[i]})),
  tasks:[{id:'rewrite',label:'Polish my writing'},{id:'email',label:'Reply to an email'},{id:'document',label:'Draft a document'}],
  formats:[{id:'document',label:'General document'},{id:'specification',label:'Technical specification'},{id:'readme',label:'README'}],
  details:[{id:'brief',label:'Overview / brief'},{id:'standard',label:'Practical detail'},{id:'detailed',label:'Comprehensive reference'}],
  max_text:12000,max_draft:16000,max_directions:2000};
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL || 'chromium'});
  try {
    const context=await browser.newContext({acceptDownloads:true,permissions:['clipboard-read','clipboard-write']});
    const page=await context.newPage(); const errors=[], requests=[];
    let mode='ok', pending;
    page.on('pageerror',err=>errors.push(err.message));
    await page.route('**/*',async route=>{
      const url=new URL(route.request().url());
      if(url.pathname==='/api/writing/options')return route.fulfill({json:options});
      if(url.pathname==='/api/writing/draft'){
        requests.push(route.request().postDataJSON());
        if(mode==='error')return route.fulfill({status:503,json:{error:'The AI is unavailable. Try again.'}});
        if(mode==='pending'){pending=route;return;}
        return route.fulfill({json:{draft:'Subject: Schedule\n\nThank you. The specification is 12 V DC, 2 A.\n<script>window.pwned=true</script>'}});
      }
      if(url.pathname.startsWith('/api/')){
        let data={};
        if(['/api/chats','/api/commands'].includes(url.pathname))data=[];
        if(url.pathname==='/api/ai-status')data={state:'ok',model:'test'};
        if(url.pathname==='/api/reminders/fired')data={items:[],latest:0};
        return route.fulfill({json:data});
      }
      const file=path.join(web,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
      if(!file.startsWith(web+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
      return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost:7770/');
    // The input keeps its full row; tools now live in the + popup.
    for (const width of [320,390,760]) {
      await page.setViewportSize({width,height:440});
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
      const layout=await page.evaluate(()=>{
        const rect=id=>document.getElementById(id).getBoundingClientRect();
        const input=rect('input'),more=rect('composer-more'),send=rect('send'),composer=document.querySelector('.composer').getBoundingClientRect();
        return {input:input.width,composer:composer.width,below:more.top>=input.bottom,sameRow:Math.abs(more.top-send.top)<1,
          bottom:send.bottom,height:innerHeight,overflow:document.body.scrollWidth>innerWidth};
      });
      assert.ok(layout.input>=layout.composer-1&&layout.below&&layout.sameRow,JSON.stringify(layout));
      assert.ok(layout.bottom<=layout.height+1&&!layout.overflow,JSON.stringify(layout));
      await page.locator('#composer-more').click();
      assert.equal(await page.locator('#writing-open').isVisible(),true);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#composer-tools').isVisible(),false);
    }
    await page.setViewportSize({width:1280,height:800});
    await page.locator('#input').fill('/rewrite'); await page.locator('#send').click();
    await page.locator('#writing-dialog').waitFor({state:'visible'});
    await page.waitForFunction(()=>document.querySelector('#writing-tone').options.length===16);
    assert.deepEqual(await page.locator('#writing-tone option').allTextContents(),labels);
    assert.equal(requests.length,0,'opening the helper must not call the AI');
    await page.locator('#writing-task').selectOption('email');
    await page.locator('#writing-tone').selectOption('diplomatic');
    await page.locator('#writing-source').fill('Can you meet on November 4?');
    await page.locator('#writing-generate').click();
    assert.equal(requests.length,0,'email replies need the user intent');
    await page.locator('#writing-instructions').fill('Decline; offer November 6.');
    await page.locator('#writing-generate').click();
    await page.waitForFunction(()=>!document.querySelector('#writing-result').hidden);
    assert.equal(requests.length,1);
    assert.equal(requests[0].tone,'diplomatic'); assert.equal(requests[0].task,'email');
    assert.equal(await page.evaluate(()=>window.pwned),undefined);
    assert.equal(await page.locator('#writing-dialog script').count(),0);
    const edited='Subject: Availability\n\nI can meet November 6.\n';
    await page.locator('#writing-draft').fill(edited);
    await page.locator('#writing-copy').click();
    assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replace(/\r\n/g,'\n'),edited);
    const downloadEvent=page.waitForEvent('download'); await page.locator('#writing-save').click();
    const download=await downloadEvent;
    assert.equal(download.suggestedFilename(),'email-reply.txt');
    assert.equal(fs.readFileSync(await download.path(),'utf8'),edited);
    await page.locator('#writing-revision').fill('Make it shorter, preserving November 6.');
    await page.locator('#writing-revise').click();
    await page.waitForFunction(()=>!document.querySelector('#writing-generate').disabled);
    assert.equal(requests[1].previous,edited);
    assert.equal(requests[1].revision,'Make it shorter, preserving November 6.');
    const before=await page.locator('#writing-draft').inputValue();
    mode='error'; await page.locator('#writing-generate').click();
    await page.waitForFunction(()=>document.querySelector('#writing-status').textContent.includes('unavailable'));
    assert.equal(await page.locator('#writing-draft').inputValue(),before);
    assert.equal(await page.locator('#writing-source').inputValue(),'Can you meet on November 4?');
    mode='pending'; await page.locator('#writing-generate').click();
    await page.waitForFunction(()=>!document.querySelector('#writing-cancel').hidden);
    await page.locator('#writing-cancel').click();
    assert.equal(await page.locator('#writing-draft').inputValue(),before);
    if(pending)await pending.fulfill({json:{draft:'Late response must be ignored'}}).catch(()=>{});
    mode='ok';
    await page.locator('#writing-task').selectOption('document');
    await page.locator('#writing-tone').selectOption('technical');
    await page.locator('#writing-source').fill('Supply 12 V DC at 2 A.');
    await page.locator('#writing-instructions').fill('Write installation documentation.');
    await page.locator('#writing-dialog summary').click();
    await page.locator('#writing-format').selectOption('readme');
    await page.locator('#writing-audience').fill('Engineers');
    await page.locator('#writing-detail').selectOption('detailed');
    await page.evaluate(()=>{chatId=1;const el=document.createElement('p');el.className='attach-line';list.prepend(el);});
    await page.locator('#writing-close').click(); await page.locator('#composer-more').click(); await page.locator('#writing-open').click();
    await page.locator('#writing-attachments').check();
    await page.locator('#writing-generate').click();
    await page.waitForFunction(()=>!document.querySelector('#writing-generate').disabled);
    const technical=requests.at(-1);
    assert.equal(technical.audience,'Engineers'); assert.equal(technical.detail,'detailed');
    assert.equal(technical.document_format,'readme'); assert.equal(technical.use_attachments,true); assert.equal(technical.chat_id,1);
    const mdEvent=page.waitForEvent('download'); await page.locator('#writing-save').click();
    assert.equal((await mdEvent).suggestedFilename(),'README.md');
    await page.screenshot({path:process.env.BEYOND_WRITING_SCREENSHOT || path.join(os.tmpdir(),'beyond-writing-desktop.png')});
    await page.setViewportSize({width:390,height:844}); await page.emulateMedia({colorScheme:'dark'});
    const sizing=await page.locator('#writing-dialog').evaluate(el=>({left:el.getBoundingClientRect().left,
      right:el.getBoundingClientRect().right,view:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}));
    assert.ok(sizing.left>=0&&sizing.right<=sizing.view&&sizing.scroll<=sizing.client+1,JSON.stringify(sizing));
    await page.screenshot({path:path.join(os.tmpdir(),'beyond-writing-mobile.png')});
    await page.locator('#writing-close').click();
    await page.evaluate(()=>{chatId=2;document.querySelector('.attach-line').remove();});
    await page.locator('#composer-more').click(); await page.locator('#writing-open').click();
    assert.equal(await page.locator('#writing-attachments').isChecked(),false);
    assert.equal(await page.locator('#writing-attachments').isDisabled(),true);
    assert.deepEqual(errors,[]);
    console.log('PASS writing helper: all tones, validation, email/document controls, revision, exact Copy/Save, error/cancel retention, attachments, safe text and mobile/dark layout.');
  }finally{await browser.close();}
})().catch(err=>{console.error(err);process.exitCode=1;});
