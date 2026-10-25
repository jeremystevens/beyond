const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
 try{
  const page=await browser.newPage(),errors=[],requests=[];let mode='ok';
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/look'){
    requests.push(Object.fromEntries(url.searchParams));
    assert.equal(route.request().method(),'POST');assert.ok(route.request().postDataBuffer().length);
    if(mode==='error')return route.fulfill({status:503,json:{error:'Run Add-Features.cmd to install a screenshot reader.'}});
    return route.fulfill({status:202,json:{chat_id:1}});
   }
   if(url.pathname==='/api/chats/1')return route.fulfill({json:{id:1,messages:[
    {id:1,role:'user',kind:'troubleshoot',content:'Troubleshoot this screenshot: after changing port'},
    {id:2,role:'assistant',kind:'troubleshoot',content:'Try first: Check the address.\nQuestions: Which app?\n<script>window.pwned=true</script>',buttons:[]}
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
  await page.locator('#photo-file').setInputFiles({name:'error.png',mimeType:'image/png',buffer:png});
  assert.ok(await page.locator('#troubleshoot-photo').isVisible());
  await page.locator('#photo-question').fill('after changing port');
  await page.locator('#troubleshoot-photo').click();
  await page.waitForFunction(()=>document.querySelector('[data-message-id="2"]'));
  assert.deepEqual(requests[0],{action:'troubleshoot',question:'after changing port',method:'auto'});
  assert.ok(await page.locator('[data-message-id="2"] .scan-copy').isVisible());
  assert.equal(await page.evaluate(()=>window.pwned),undefined);
  assert.ok((await page.locator('#log').textContent()).includes('Which app?'));
  await page.locator('#photo-file').setInputFiles({name:'error.png',mimeType:'image/png',buffer:png});
  await page.locator('#troubleshoot-method').selectOption('vision');mode='error';
  await page.locator('#troubleshoot-photo').click();
  await page.waitForFunction(()=>document.querySelector('#log').textContent.includes('Add-Features.cmd'));
  assert.equal(requests.at(-1).method,'vision');assert.equal(requests.at(-1).chat_id,'1');
  assert.ok(await page.locator('#photo-preview').isVisible());
  assert.equal(await page.locator('#troubleshoot-photo').isDisabled(),false);
  await page.locator('#remove-photo').click();
  await page.locator('#input').evaluate(el=>{
    const data=new DataTransfer();data.items.add(new File([new Uint8Array([1,2,3])],'clipboard.png',{type:'image/png'}));
    el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));
  });
  assert.ok(await page.locator('#photo-preview').isVisible(),'clipboard image enters the same preview');
  for(const width of [320,390]){
   await page.setViewportSize({width,height:640});
   await page.emulateMedia({colorScheme:'dark'});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,'no mobile overflow');
  }
  assert.deepEqual(errors,[]);
  console.log('PASS screenshot troubleshooting: attachment/paste, action/context/reader, saved result, safe text, missing-feature recovery and mobile layout.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
