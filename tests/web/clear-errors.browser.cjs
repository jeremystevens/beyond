const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
 try{
  const page=await browser.newPage(); let deletes=0,fail=false,admin=true;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const items=[{id:7,created_at:'2026-10-25T10:00:00Z',source:'server',summary:'A request failed.'}];
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/auth/state')return route.fulfill({json:{admin}});
   if(url.pathname==='/api/status/errors'){
    if(route.request().method()==='DELETE'){
     deletes++;
     if(fail)return route.fulfill({status:503,json:{error:'Error history could not be cleared. Please try again.'}});
     return route.fulfill({json:{cleared:1,items:[]}});
    }
    return route.fulfill({json:{items}});
   }
   if(url.pathname==='/api/status/speed')return route.fulfill({json:{items:[],models:[]}});
   if(url.pathname.startsWith('/api/'))return route.fulfill({status:503,json:{error:'Not used in this test'}});
   const file=url.pathname==='/status'?path.join(web,'status.html'):path.resolve(web,url.pathname.replace(/^\/static\//,''));
   if(!file.startsWith(web+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
   return route.fulfill({path:file,contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://beyond.test/status');
  await page.locator('#auto').uncheck();
  const clear=page.locator('#clear-error-history');
  await clear.waitFor({state:'visible'});
  await page.waitForFunction(()=>!document.querySelector('#clear-error-history').disabled);
  page.once('dialog',dialog=>dialog.dismiss());
  await clear.click();assert.equal(deletes,0);assert.equal(await page.locator('#errors .item').count(),1);
  fail=true;page.once('dialog',dialog=>dialog.accept());await clear.click();
  await page.waitForFunction(()=>document.querySelector('#clear-error-note').textContent.includes('could not'));
  assert.equal(deletes,1);assert.equal(await page.locator('#errors .item').count(),1);
  fail=false;page.once('dialog',dialog=>dialog.accept());await clear.click();
  await page.waitForFunction(()=>document.querySelector('#clear-error-note').textContent.includes('1 saved'));
  assert.equal(deletes,2);assert.equal(await page.locator('#errors .item').count(),0);
  assert.equal(await page.locator('#error-empty').isVisible(),true);
  admin=false;await page.reload();await page.waitForFunction(()=>!document.querySelector('#refresh').disabled);
  assert.equal(await clear.isVisible(),false);assert.deepEqual(errors,[]);
  console.log('Clear errors: cancel, failure, success and permissions passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
