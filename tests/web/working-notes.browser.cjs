const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
 try{
  const page=await browser.newPage(),errors=[];let drafts=0,saves=0,reads=0,fail=false;
  let notes={text:'',enabled:false,revision:0,covered_id:0,invalidated:false,new_messages:2,fingerprint:'a'.repeat(64)};
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname.endsWith('/working-notes/draft')){
    drafts++;if(fail)return route.fulfill({status:503,json:{error:'The AI is unavailable. Saved notes are unchanged.'}});
    return route.fulfill({json:{text:'Goal: party. Decisions: Tuesday.\n<script>window.pwned=true</script>',fingerprint:notes.fingerprint,partial:true,used_messages:4,total_messages:20}});
   }
   if(url.pathname.endsWith('/working-notes/pause')){
    const data=route.request().postDataJSON();notes={...notes,enabled:false,revision:notes.revision+1,text:data.clear?'':notes.text};return route.fulfill({json:notes});
   }
   if(url.pathname.endsWith('/working-notes')){
    if(route.request().method()==='PUT'){
     saves++;const body=route.request().postDataJSON();notes={...notes,text:body.text,enabled:body.enabled,revision:notes.revision+1,new_messages:0};
    }else reads++;
    return route.fulfill({json:notes});
   }
   if(url.pathname==='/api/chats/1')return route.fulfill({json:{id:1,messages:[{id:1,role:'user',kind:'chat',content:'Budget $200.'},{id:2,role:'assistant',kind:'chat',content:'Tuesday?',buttons:[]}]}});
   if(url.pathname.startsWith('/api/')){
    let data={};if(['/api/chats','/api/commands'].includes(url.pathname))data=[];
    if(url.pathname==='/api/ai-status')data={state:'ok'};
    if(url.pathname==='/api/reminders/fired')data={items:[],latest:0};return route.fulfill({json:data});
   }
   const file=path.join(web,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
   if(!file.startsWith(web+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
   return route.fulfill({path:file,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost:7770/');await page.evaluate(()=>openChat(1));
  assert.equal(reads,0);assert.equal(drafts,0);
  await page.locator('#notes-open').click();await page.waitForFunction(()=>!document.querySelector('#notes-draft').disabled);
  assert.equal(drafts,0,'opening notes must not generate a draft');
  await page.locator('#notes-draft').click();await page.waitForFunction(()=>document.querySelector('#notes-status').textContent.startsWith('Draft only'));
  assert.equal(saves,0,'drafts are not activated or saved automatically');assert.equal(notes.enabled,false);
  assert.equal(await page.evaluate(()=>window.pwned),undefined);assert.equal(await page.locator('#notes-dialog script').count(),0);
  await page.locator('#notes-text').fill('Goal: party. Decisions: Wednesday.');await page.locator('#notes-save').click();
  await page.waitForFunction(()=>document.querySelector('#notes-status').textContent.includes('in use'));
  assert.equal(saves,1);assert.ok(notes.text.includes('Wednesday'));
  await page.locator('#notes-pause').click();await page.waitForFunction(()=>document.querySelector('#notes-status').textContent.includes('paused'));
  assert.equal(notes.enabled,false);assert.ok(notes.text.includes('Wednesday'));
  fail=true;await page.locator('#notes-draft').click();await page.waitForFunction(()=>document.querySelector('#notes-status').textContent.includes('unavailable'));
  assert.ok((await page.locator('#notes-text').inputValue()).includes('Wednesday'));
  for(const width of [320,390,760]){
   await page.setViewportSize({width,height:440});await page.emulateMedia({colorScheme:'dark'});
   const bounds=await page.locator('#notes-dialog').evaluate(el=>({right:el.getBoundingClientRect().right,width:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}));
   assert.ok(bounds.right<=bounds.width&&bounds.scroll<=bounds.client+1,JSON.stringify(bounds));
   assert.ok((await page.locator('#notes-save').boundingBox()).height>=44);
  }
  page.once('dialog',dialog=>dialog.accept());await page.locator('#notes-clear').click();
  await page.waitForFunction(()=>document.querySelector('#notes-text').value==='');assert.equal(notes.text,'');
  await page.locator('#notes-close').click();await page.evaluate(()=>newChat());
  assert.equal(await page.locator('#recap-tools').isVisible(),false);assert.deepEqual(errors,[]);
  console.log('Working notes: explicit drafts, review/save, pause, errors, clear and mobile layouts passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
