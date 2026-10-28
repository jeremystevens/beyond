const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const web=path.resolve(__dirname,'../../app/web');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.BEYOND_BROWSER_CHANNEL||'chromium'});
 try {
  const context=await browser.newContext({acceptDownloads:true});
  const page=await context.newPage(),errors=[],sent=[];let speechEnabled=true;
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{
   window.fakeVoice={loud:false,tracks:[],players:[],htmlAudioPlays:0};
   Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:async()=>{
    const track={stopped:false,stop(){this.stopped=true;}};window.fakeVoice.tracks.push(track);return {getTracks:()=>[track]};
   }}});
   window.MediaRecorder=class {constructor(){this.state='inactive';this.mimeType='audio/webm';}start(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['sample'])});this.onstop?.();}};
   window.AudioContext=class {constructor(){this.state='running';}createAnalyser(){return {fftSize:512,getByteTimeDomainData(data){data.fill(window.fakeVoice.loud?150:128);}};}
    createMediaStreamSource(){return {connect(){}};}close(){return Promise.resolve();}};
   window.Audio=class {constructor(url){this.url=url;this.listeners={};this.playCount=0;window.fakeVoice.players.push(this);}
    addEventListener(name,fn){this.listeners[name]=fn;}async play(){this.playCount++;if(window.fakeVoice.tracks.some(t=>!t.stopped))throw new Error('Microphone active during playback');}
    pause(){}removeAttribute(){}end(){this.listeners.ended?.();}};
   HTMLMediaElement.prototype.play=function(){window.fakeVoice.htmlAudioPlays++;return Promise.resolve();};
   HTMLMediaElement.prototype.pause=function(){};
  });
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/settings')return route.fulfill({json:{values:{speech_enabled:speechEnabled}}});
   if(url.pathname==='/api/transcribe')return route.fulfill({json:{text:'Hello by voice.',seconds:1}});
   if(url.pathname==='/api/chat/stream'){
    sent.push(route.request().postDataJSON());
    return route.fulfill({contentType:'application/x-ndjson',body:[{type:'chat',id:1,new:sent.length===1,question_id:1},
      {type:'token',text:'Hello from BEYOND.'},{type:'message',id:2,buttons:[],speech:{state:'pending'},speakable:true,speak_requested:true},
      {type:'done'}].map(x=>JSON.stringify(x)).join('\n')+'\n'});
   }
   if(url.pathname==='/api/speech'&&route.request().method()==='POST')return route.fulfill({json:{state:'ready',url:'/api/speech/2.wav'}});
   if(url.pathname==='/api/speech/status')return route.fulfill({json:{items:[{id:2,state:'ready',url:'/api/speech/2.wav'}],auto_read:true}});
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
  for(const width of [320,390,1280]){
   await page.setViewportSize({width,height:700});
   await page.locator('#composer-more').click();
   assert.equal(await page.locator('#voice-conversation-open').isVisible(),true);
   const positions=await page.evaluate(()=>['mic','voice-conversation-open','writing-open'].map(id=>{
    const el=document.getElementById(id);return [el.querySelector('svg').getBoundingClientRect().left,el.querySelector('span').getBoundingClientRect().left];}));
   assert.ok(Math.max(...positions.map(p=>p[0]))-Math.min(...positions.map(p=>p[0]))<1);
   assert.ok(Math.max(...positions.map(p=>p[1]))-Math.min(...positions.map(p=>p[1]))<1);
   await page.locator('#voice-conversation-open').click();
   assert.equal(await page.locator('#voice-conversation-setup').isVisible(),true);
   assert.equal(await page.locator('#voice-save-transcript').isChecked(),false);
   await page.locator('#voice-setup-close').click();
  }
  await page.setViewportSize({width:320,height:700});
  await page.locator('#composer-more').click();await page.locator('#voice-conversation-open').click();
  await page.locator('#voice-save-transcript').check();await page.locator('#voice-setup-start').click();
  await page.getByText('Listening…',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.evaluate(()=>window.fakeVoice.loud=true);await page.waitForTimeout(500);
  await page.evaluate(()=>window.fakeVoice.loud=false);
  await page.getByText('Speaking…',{exact:true}).waitFor({timeout:10000});
  assert.equal(sent.length,1);assert.equal(sent[0].content,'Hello by voice.');
  assert.equal(await page.evaluate(()=>window.fakeVoice.tracks.every(t=>t.stopped)),true);
  await page.waitForTimeout(2500);
  assert.equal(await page.evaluate(()=>window.fakeVoice.htmlAudioPlays),0,'automatic read-aloud must not duplicate voice playback');
  await page.locator('#voice-session-pause').click();assert.equal(await page.locator('#voice-session-pause').textContent(),'Resume');
  await page.locator('#voice-session-pause').click();
  await page.evaluate(()=>window.fakeVoice.players[0].end());
  await page.getByText('Listening…',{exact:true}).waitFor();
  await page.locator('#voice-session-end').click();
  assert.equal(await page.evaluate(()=>window.fakeVoice.tracks.every(t=>t.stopped)),true);
  await page.locator('#voice-conversation-export').waitFor({state:'visible'});
  const downloadEvent=page.waitForEvent('download');await page.locator('#voice-export-save').click();
  const download=await downloadEvent;assert.equal(download.suggestedFilename(),'beyond-voice-transcript.txt');
  const transcript=fs.readFileSync(await download.path(),'utf8');assert.match(transcript,/You: Hello by voice\./);assert.match(transcript,/BEYOND: Hello from BEYOND\./);
  // Changing chats ends an active session, releases the microphone, and does not offer a disabled transcript.
  await page.locator('#composer-more').click();await page.locator('#voice-conversation-open').click();
  await page.locator('#voice-setup-start').click();await page.getByText('Listening…',{exact:true}).waitFor();
  await page.evaluate(() => document.querySelector('#newchat').click());
  assert.equal(await page.locator('#voice-session').isVisible(),false);
  assert.equal(await page.locator('#voice-conversation-export').isVisible(),false);
  assert.equal(await page.evaluate(()=>window.fakeVoice.tracks.every(t=>t.stopped)),true);
  speechEnabled=false;await page.locator('#composer-more').click();await page.locator('#voice-conversation-open').click();
  await page.locator('#voice-setup-start').click();await page.waitForFunction(()=>document.querySelector('#voice-setup-error').textContent.includes('Spoken replies'));assert.match(await page.locator('#voice-setup-error').textContent(),/Spoken replies/);
  await page.locator('#voice-setup-close').click();assert.deepEqual(errors,[]);
  console.log('Voice conversation UI, microphone lifecycle, transcript, mobile layout and playback passed.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
