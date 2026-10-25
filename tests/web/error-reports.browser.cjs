const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'beyond-report-'));
 try{
  const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']});
  const page=await context.newPage(),errors=[],reports=[];let fail=false,simulated=true,checks=0;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname.endsWith('/report')){
    reports.push(route.request().postDataJSON());
    if(fail)return route.fulfill({status:404,json:{detail:'This error is no longer in recent history.'}});
    return route.fulfill({json:{filename:'beyond-error-report-7.txt',text:'BEYOND local error report\n[secret removed]\n<script>window.pwned=true</script>\n',simulated}});
   }
   if(url.pathname.endsWith('/github/check')){
    checks++;return route.fulfill({json:{checked:true,note:'Possible matches only.',needs_paste:false,
      draft_url:'https://github.com/jeremystevens/beyond/issues/new?title=Report',
      matches:[{number:123,state:'open',title:'<script>window.pwned=true</script>',match:'Similar category',url:'https://github.com/jeremystevens/beyond/issues/123'}]}});
   }
   if(url.pathname.startsWith('/api/')){
    let data={};
    if(url.pathname==='/api/status')data={at:'2026-10-25T04:00:00Z',version:'1.1.0',ai:{state:'off'},services:[],
     system:{cpu_percent:1,logical_cpus:8,memory_percent:50,memory_total:16000000000,memory_available:8000000000,
       disk_total:100000000000,disk_free:50000000000,app_uptime_seconds:60}};
    if(url.pathname==='/api/status/speed')data={items:[],models:[]};
    if(url.pathname==='/api/status/errors')data={items:[{id:7,source:'Diagnostic test',summary:'Simulated timeout',created_at:'2026-10-25T04:00:00Z'}]};
    return route.fulfill({json:data});
   }
   const file=path.join(web,url.pathname==='/status'?'status.html':url.pathname.replace(/^\/static\//,''));
   if(!file.startsWith(web+path.sep)||!fs.existsSync(file))return route.fulfill({status:404,body:''});
   return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://localhost:7770/status');
  await page.locator('.report-button').click();
  assert.equal(reports.length,0,'opening Report must not collect a report automatically');
  assert.equal(await page.locator('#report-copy').isDisabled(),true);
  await page.locator('#report-happened').fill('The app stopped. password=secret');
  await page.locator('#report-expected').fill('A reply.');
  await page.locator('#report-environment').uncheck();
  await page.locator('#report-build').click();
  await page.waitForFunction(()=>!document.querySelector('#report-copy').disabled);
  assert.equal(reports[0].include_environment,false);assert.ok(reports[0].happened.includes('password='));
  assert.equal(await page.evaluate(()=>window.pwned),undefined);
  assert.equal(await page.locator('#report-preview script').count(),0);
  assert.ok((await page.locator('#report-status').textContent()).includes('SIMULATED'));
  const edited='Reviewed report\nMy exact edits: café and <b>literal text</b>\n';
  await page.locator('#report-preview').fill(edited);await page.locator('#report-copy').click();
  // Windows clipboard uses CRLF; compare content with only the platform line endings normalized.
  assert.equal((await page.evaluate(()=>navigator.clipboard.readText())).replace(/\r\n/g,'\n'),edited);
  const downloadPromise=page.waitForEvent('download');await page.locator('#report-save').click();
  const download=await downloadPromise;assert.equal(download.suggestedFilename(),'beyond-error-report-7.txt');
  const target=path.join(dir,'report.txt');await download.saveAs(target);assert.equal(fs.readFileSync(target,'utf8'),edited);
  await page.locator('#report-tried').fill('Restarted.');
  assert.equal(await page.locator('#report-save').isDisabled(),true,'changed notes must invalidate export until rebuilt');
  fail=true;await page.locator('#report-build').click();
  await page.waitForFunction(()=>document.querySelector('#report-status').textContent.includes('no longer'));
  assert.equal(await page.locator('#report-copy').isDisabled(),true);
  for(const width of [320,390]){
   await page.setViewportSize({width,height:440});await page.emulateMedia({colorScheme:'dark'});
   const bounds=await page.locator('#report-dialog').evaluate(el=>({right:el.getBoundingClientRect().right,width:innerWidth,
     scroll:el.scrollWidth,client:el.clientWidth,bottom:el.getBoundingClientRect().bottom,height:innerHeight}));
   assert.ok(bounds.right<=bounds.width&&bounds.scroll<=bounds.client+1&&bounds.bottom<=bounds.height+1);
  }
  assert.equal(await page.locator('#report-github').isDisabled(),true,'simulated errors stay local');
  await page.locator('#report-close').click();
  simulated=false;fail=false;await page.locator('.report-button').click();await page.locator('#report-build').click();
  await page.waitForFunction(()=>!document.querySelector('#report-github').disabled);
  assert.equal(checks,0,'no automatic GitHub search');
  await page.locator('#report-github').click();await page.waitForFunction(()=>!document.querySelector('#report-github-next').hidden);
  assert.equal(checks,1);assert.equal(await page.evaluate(()=>window.pwned),undefined);
  assert.equal(await page.locator('#report-github-results a').count(),1);
  assert.equal(await page.locator('#report-github-next').getAttribute('rel'),'noopener noreferrer');
  await page.locator('#report-preview').fill('Edited report after check');
  assert.equal(await page.locator('#report-github-next').isVisible(),false,'edits invalidate GitHub handoff');
  await page.locator('#report-close').click();assert.equal(await page.locator('#report-dialog').isVisible(),false);
  assert.deepEqual(errors,[]);
  console.log('PASS local error reports: on-demand preview, notes/options, safe editable text, exact Copy/Save, stale/expired errors and mobile dark layout.');
 }finally{await browser.close();fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
