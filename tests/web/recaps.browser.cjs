const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
(async()=>{
  const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
  try{
    const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']});
    const page=await context.newPage(),errors=[],requests=[];
    let generation=0,mode='ok';
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/*',async route=>{
      const url=new URL(route.request().url());
      if(url.pathname.endsWith('/recap')){
        const body=route.request().postDataJSON();requests.push(body);
        if(mode==='error')return route.fulfill({status:503,json:{error:'The AI is unavailable. Try again.'}});
        const cached=generation>0&&!body.refresh;if(!cached)generation++;
        return route.fulfill({json:{text:'Topic: test plan\nDecisions: option B.\nOpen questions: color.\n<script>window.pwned=true</script>',
          cached,saved:true,partial:true,used_messages:4,total_messages:50}});
      }
      if(url.pathname==='/api/chats/1')return route.fulfill({json:{id:1,messages:[
        {id:1,role:'user',kind:'chat',content:'We chose option B.'},
        {id:2,role:'assistant',kind:'chat',content:'What color?',buttons:[]}
      ]}});
      if(url.pathname.startsWith('/api/')){
        let data={};if(['/api/chats','/api/commands'].includes(url.pathname))data=[];
        if(url.pathname==='/api/ai-status')data={state:'ok'};
        if(url.pathname==='/api/reminders/fired')data={items:[],latest:0};
        return route.fulfill({json:data});
      }
      const file=path.join(web,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
      if(!file.startsWith(web+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
      return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
    });
    await page.goto('http://localhost:7770/');
    assert.equal(await page.locator('#recap-tools').isVisible(),false);
    await page.evaluate(()=>openChat(1));
    assert.equal(requests.length,0,'opening a chat must not generate or fetch a recap');
    await page.locator('#recap-open').click();
    await page.waitForFunction(()=>document.querySelector('#recap-status').textContent.startsWith('New recap'));
    assert.ok((await page.locator('#recap-status').textContent()).includes('4 of 50'));
    assert.equal(await page.evaluate(()=>window.pwned),undefined);
    assert.equal(await page.locator('#recap-text script').count(),0);
    await page.locator('#recap-copy').click();
    assert.ok((await page.evaluate(()=>navigator.clipboard.readText())).includes('option B'));
    await page.locator('#recap-close').click();await page.locator('#recap-open').click();
    await page.waitForFunction(()=>document.querySelector('#recap-status').textContent.startsWith('Saved recap'));
    assert.equal(generation,1);
    await page.locator('#recap-refresh').click();
    await page.waitForFunction(()=>!document.querySelector('#recap-refresh').disabled);
    assert.equal(generation,2);assert.equal(requests.at(-1).refresh,true);
    mode='error';await page.locator('#recap-refresh').click();
    await page.waitForFunction(()=>document.querySelector('#recap-status').textContent.includes('unavailable'));
    assert.equal(await page.locator('#recap-text').textContent(),'','old text must not be presented as current after a failed request');
    await page.setViewportSize({width:390,height:440});await page.emulateMedia({colorScheme:'dark'});
    const bounds=await page.locator('#recap-dialog').evaluate(el=>({right:el.getBoundingClientRect().right,
      width:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}));
    assert.ok(bounds.right<=bounds.width&&bounds.scroll<=bounds.client+1);
    await page.locator('#recap-close').click();await page.evaluate(()=>newChat());
    assert.equal(await page.locator('#recap-tools').isVisible(),false);
    assert.equal(await page.locator('#recap-text').textContent(),'');
    assert.deepEqual(errors,[]);
    console.log('PASS recap UI: on-demand only, cache/refresh, coverage warning, Copy, literal safe text, errors, chat switching and mobile dark layout.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
