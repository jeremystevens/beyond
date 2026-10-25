const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
 try{
  const page=await browser.newPage(),errors=[],requests=[];let fail=false;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/messages/2/check'){
    if(route.request().method()==='GET')return route.fulfill({json:{claim:'2+2=5',has_documents:true,truncated:false}});
    const body=route.request().postDataJSON();requests.push(body);
    if(fail)return route.fulfill({status:503,json:{error:'Search is unavailable. No claim was verified.'}});
    return route.fulfill({json:{evidence:'2 + 2 = 4\n<script>window.pwned=true</script>',assessment:'Does not match.',
      method:'Calculator',limit:'Selected expression only.',ai_used:false,at:'2026-10-25T10:00:00Z',sources:['https://example.com/fact','javascript:alert(1)']}});
   }
   if(url.pathname==='/api/chats/1')return route.fulfill({json:{id:1,messages:[{id:1,role:'user',kind:'chat',content:'2+2?'},
    {id:2,role:'assistant',kind:'chat',content:'2+2=5',buttons:[[{label:'Try again',action:'rate:retry:2'}]]}]}});
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
  assert.equal(requests.length,0,'normal chat opening does not run checks');
  await page.locator('[data-kind="adjust"]').click();await page.getByRole('button',{name:'Check answer',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('#check-run').disabled);
  await page.locator('#check-expression').fill('2+2=5');await page.locator('#check-run').click();
  await page.waitForFunction(()=>!document.querySelector('#check-result').hidden);
  assert.equal(requests[0].mode,'math');assert.equal(await page.evaluate(()=>window.pwned),undefined);
  assert.equal(await page.locator('#check-evidence script').count(),0);assert.equal(await page.locator('#check-sources a').count(),1);
  await page.locator('#check-expression').fill('3+3');assert.equal(await page.locator('#check-result').isVisible(),false);
  await page.locator('#check-mode').selectOption('web');assert.equal(requests.length,1,'choosing web never searches by itself');
  await page.locator('#check-query').fill('public fact');fail=true;await page.locator('#check-run').click();
  await page.waitForFunction(()=>document.querySelector('#check-status').textContent.includes('unavailable'));
  assert.equal(await page.locator('#check-result').isVisible(),false);
  for(const width of [320,390,760]){
   await page.setViewportSize({width,height:440});await page.emulateMedia({colorScheme:'dark'});
   const bounds=await page.locator('#check-dialog').evaluate(el=>({right:el.getBoundingClientRect().right,width:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}));
   assert.ok(bounds.right<=bounds.width&&bounds.scroll<=bounds.client+1,JSON.stringify(bounds));
   assert.ok((await page.locator('#check-run').boundingBox()).height>=44);
  }
  await page.locator('#check-close').click();assert.equal(await page.locator('#check-dialog').isVisible(),false);
  assert.deepEqual(errors,[]);console.log('Answer checks: explicit actions, safe rendering, errors and mobile layouts passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
