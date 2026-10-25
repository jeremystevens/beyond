const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
 try{
  const page=await browser.newPage(),errors=[],sent=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/chat/stream'){
    const body=route.request().postDataJSON();sent.push(body);
    return route.fulfill({contentType:'application/x-ndjson',body:[{type:'chat',id:1,new:true,question_id:1,think_through:body.think_through},
      {type:'status',text:'Think it through: checking the requirements…'},{type:'token',text:'Final answer'},
      {type:'message',id:2,buttons:[]},{type:'done'}].map(e=>JSON.stringify(e)).join('\n')+'\n'});
   }
   if(url.pathname==='/api/chats/1')return route.fulfill({json:{id:1,messages:[],attachments:[]}});
   if(url.pathname.startsWith('/api/')){
    let data={};if(['/api/chats','/api/commands'].includes(url.pathname))data=[];
    if(url.pathname==='/api/ai-status')data={state:'ok'};
    if(url.pathname==='/api/reminders/fired')data={items:[],latest:0};return route.fulfill({json:data});
   }
   const file=path.join(web,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
   if(!file.startsWith(web+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
   return route.fulfill({path:file,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost:7770/');
  assert.equal(await page.locator('#composer-tools').isVisible(),false);
  assert.equal(await page.locator('#attach-photo').isVisible(),false);
  assert.equal(await page.locator('#think-indicator').isVisible(),false);
  for(const width of [320,390,760,1280]){
   await page.setViewportSize({width,height:440});await page.emulateMedia({colorScheme:'dark'});
   await page.locator('#composer-more').click();
   for(const id of ['attach-photo','mic','writing-open'])assert.equal(await page.locator('#'+id).isVisible(),true);
   const box=await page.locator('#composer-tools').evaluate(el=>({left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right,width:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}));
   assert.ok(box.left>=0&&box.right<=box.width&&box.scroll<=box.client+1,JSON.stringify(box));
   assert.ok((await page.locator('#attach-photo').boundingBox()).height>=44);
   await page.keyboard.press('Escape');assert.equal(await page.locator('#composer-tools').isVisible(),false);
   assert.equal(await page.locator('#composer-more').evaluate(el=>document.activeElement===el),true);
  }
  await page.locator('#composer-more').click();await page.locator('#think-mode').check();
  await page.locator('#input').click();assert.equal(await page.locator('#composer-tools').isVisible(),false);
  assert.equal(await page.locator('#think-indicator').isVisible(),true);
  await page.locator('#input').fill('Plan a simple project.');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelector('#send').textContent==='Send');
  assert.equal(sent[0].think_through,true);assert.equal(await page.locator('.think-label').count(),1);
  await page.reload();assert.equal(await page.locator('#think-indicator').isVisible(),true);
  await page.locator('#think-indicator').click();assert.equal(await page.locator('#think-indicator').isVisible(),false);
  await page.locator('#input').fill('/think Compare options.');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelector('#send').textContent==='Send');
  assert.equal(sent[1].think_through,true);assert.equal(sent[1].content,'Compare options.');
  assert.equal(await page.locator('#think-indicator').isVisible(),false,'one-off command must not enable sticky mode');
  await page.locator('#input').fill('Hello');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelector('#send').textContent==='Send');assert.equal(sent[2].think_through,false);
  await page.locator('#input').fill('/think /files');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelector('#send').textContent==='Send');
  assert.equal(sent[3].content,'/think /files','nested commands must reach the server guard unchanged');
  await page.evaluate(()=>document.querySelector('#mic').classList.add('recording'));
  await page.locator('#voice-indicator').waitFor({state:'visible'});
  assert.equal(await page.locator('#composer-tools').isVisible(),false);
  await page.evaluate(()=>document.querySelector('#mic').classList.remove('recording'));
  await page.locator('#voice-indicator').waitFor({state:'hidden'});
  await page.locator('#composer-more').click();
  const chooserEvent=page.waitForEvent('filechooser');await page.locator('#attach-photo').click();const chooser=await chooserEvent;await chooser.setFiles([]);
  assert.equal(await page.locator('#composer-tools').isVisible(),false);
  assert.deepEqual(errors,[]);console.log('Composer: compact tools, mobile layout, mode persistence, one-off command and recording visibility passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
