const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync(require('node:path').resolve(__dirname,'../../app/web/voice-conversation.js'),'utf8');

function fixture(options={}) {
  const ids=['voice-conversation-setup','voice-conversation-export','voice-session','voice-session-status','voice-session-pause',
    'voice-conversation-open','voice-setup-error','voice-save-transcript','voice-setup-close','voice-setup-start',
    'voice-session-end','voice-export-summary','voice-export-save','voice-export-close'];
  const elements = Object.fromEntries(ids.map(id=>[id, {
    id, dataset:{}, hidden:false, checked:false, open:false, textContent:'', events:{},
    showModal(){this.open=true;}, close(){this.open=false;this.events.close?.();},
    addEventListener(name,fn){this.events[name]=fn;}, scrollIntoView(){},
  }]));
  const state={tracks:[],sent:[],players:[],intervals:new Map(),clock:0,next:1,loud:false,blob:null,stops:0,fetches:[],chatBusy:false};
  class FakeDate extends Date { static now(){return state.clock;} }
  class FakeRecorder {
    constructor(){this.state='inactive';this.mimeType='audio/webm';}
    start(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['audio'])});this.onstop?.();}
  }
  class FakeContext {
    constructor(){this.state='running';}
    createAnalyser(){return {fftSize:512,getByteTimeDomainData(data){data.fill(state.loud?150:128);}};}
    createMediaStreamSource(){return {connect(){}};}
    close(){return Promise.resolve();}
  }
  class FakeAudio {
    constructor(url){this.url=url;this.events={};this.playCalls=0;this.paused=false;state.players.push(this);}
    addEventListener(name,fn){this.events[name]=fn;}
    async play(){this.playCalls++; assert.equal(state.tracks.filter(t=>!t.stopped).length,0,'mic must be off during playback');
      if(options.blockPlayback && this.playCalls===1) throw new Error('blocked'); this.paused=false;}
    pause(){this.paused=true;}
    removeAttribute(){}
    ended(){this.events.ended?.();}
  }
  const document={hidden:false,events:{},getElementById:id=>elements[id],addEventListener(name,fn){this.events[name]=fn;},
    body:{append(){}},createElement(){return {click(){},remove(){}};}};
  const navigator={wakeLock:options.wakeLock ? {async request(){state.wakeRequests=(state.wakeRequests||0)+1;return {addEventListener(){},async release(){state.wakeReleases=(state.wakeReleases||0)+1;}};}} : undefined,mediaDevices:{async getUserMedia(){
    if(options.deny)throw Object.assign(new Error('denied'),{name:'NotAllowedError'});
    const track={stopped:false,stop(){this.stopped=true;}};state.tracks.push(track);
    if(options.holdMic)return new Promise(resolve=>{state.releaseMic=()=>resolve({getTracks:()=>[track]});});
    return {getTracks:()=>[track]};
  }}};
  const adapter={isBusy:()=>state.chatBusy,getChatId:()=>42,stopOwned(){state.stops++;},stopOtherAudio(){},onActive(){},
    async send(text,own){state.sent.push(text);own(101,'Hello back.');return {id:101,text:'Hello back.'};}};
  const fetch=async (url, init={})=>{
    state.fetches.push(url);
    if(url==='/api/settings')return {ok:true,json:async()=>({values:{speech_enabled:options.speechEnabled!==false}})};
    if(url==='/api/transcribe' && options.holdTranscription) return new Promise((resolve,reject)=>{ state.releaseTranscription=()=>resolve({ok:true,json:async()=>({text:'Too late'})}); init.signal.addEventListener('abort',()=>{state.transcriptionAborted=true;reject(Object.assign(new Error('aborted'),{name:'AbortError'}));},{once:true}); });
    if(url==='/api/transcribe')return options.transcriptionError
      ? {ok:false,json:async()=>({error:'Voice input is not installed.'})}
      : {ok:true,json:async()=>({text:options.words?.shift() || 'Hello there.'})};
    if(url==='/api/speech')return {ok:true,json:async()=>({state:'ready',url:'/sample.wav'})};
    throw new Error('Unexpected request '+url);
  };
  const sandbox={document,navigator,fetch,Audio:FakeAudio,MediaRecorder:FakeRecorder,AudioContext:FakeContext,Blob,AbortController,
    Uint8Array,Math,Promise,Date:FakeDate,URL:{createObjectURL(blob){state.blob=blob;return 'blob:test';},revokeObjectURL(){}},
    setInterval(fn){const id=state.next++;state.intervals.set(id,fn);return id;},clearInterval(id){state.intervals.delete(id);},
    setTimeout(fn){return 0;},addEventListener(name,fn){this.events[name]=fn;},events:{},isSecureContext:true};
  sandbox.window=sandbox;vm.runInNewContext(source,sandbox);
  const voice=sandbox.BeyondVoiceConversation.init(adapter);
  const flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
  async function tick(count,loud){state.loud=loud;for(let i=0;i<count;i++){state.clock+=100;for(const fn of [...state.intervals.values()])fn();await flush();}}
  async function start(transcript=false){elements['voice-conversation-open'].onclick();elements['voice-save-transcript'].checked=transcript;await elements['voice-setup-start'].onclick();await flush();}
  return {state,elements,document,voice,start,tick,flush};
}

test('conversation detects a turn, releases microphone before playback and exports both sides',async()=>{
  const f=fixture();await f.start(true);
  assert.equal(f.elements['voice-session-status'].textContent,'Listening…');
  await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.deepEqual(f.state.sent,['Hello there.']);assert.equal(f.elements['voice-session-status'].textContent,'Speaking…');
  assert.equal(f.state.tracks.every(t=>t.stopped),true);assert.equal(f.voice.owns(101),true);
  f.voice.pause();assert.equal(f.state.players[0].paused,true);assert.equal(f.elements['voice-session-pause'].textContent,'Resume');
  await f.elements['voice-session-pause'].onclick();await f.flush();assert.equal(f.state.players[0].playCalls,2);
  f.state.players[0].ended();await f.flush();assert.equal(f.elements['voice-session-status'].textContent,'Listening…');
  f.voice.end();assert.equal(f.state.tracks.every(t=>t.stopped),true);assert.equal(f.elements['voice-conversation-export'].open,true);
  f.elements['voice-export-save'].onclick();const saved=await f.state.blob.text();
  assert.match(saved,/You: Hello there\./);assert.match(saved,/BEYOND: Hello back\./);
});

test('pause and backgrounding release the microphone and discard unsent audio',async()=>{
  const f=fixture();await f.start();await f.tick(5,true);
  f.document.hidden=true;f.document.events.visibilitychange();await f.tick(20,false);
  assert.equal(f.state.tracks.every(t=>t.stopped),true);assert.deepEqual(f.state.sent,[]);
  assert.match(f.elements['voice-session-status'].textContent,/background/);
  f.voice.end();assert.equal(f.elements['voice-conversation-export'].open,false);
});

test('permission, missing speech and transcription failures are actionable',async()=>{
  let f=fixture({speechEnabled:false});await f.start();assert.match(f.elements['voice-setup-error'].textContent,/Spoken replies/);assert.equal(f.state.tracks.length,0);
  f=fixture({deny:true});await f.start();await f.flush();assert.match(f.elements['voice-session-status'].textContent,/permission was denied/);
  f=fixture({transcriptionError:true});await f.start();await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.match(f.elements['voice-session-status'].textContent,/not installed/);assert.equal(f.state.tracks.every(t=>t.stopped),true);assert.equal(f.state.sent.length,0);
});

test('blocked autoplay pauses for an explicit resume without listening over the reply',async()=>{
  const f=fixture({blockPlayback:true});await f.start();await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.match(f.elements['voice-session-status'].textContent,/Tap Resume/);assert.equal(f.state.tracks.every(t=>t.stopped),true);
  await f.elements['voice-session-pause'].onclick();assert.equal(f.state.players[0].playCalls,2);f.voice.end();
});

test('pausing during transcription cancels the request and cannot send a stale turn',async()=>{
  const f=fixture({holdTranscription:true});await f.start();await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.equal(f.elements['voice-session-status'].textContent,'Transcribing…');
  f.voice.pause();await f.flush();assert.equal(f.state.transcriptionAborted,true);
  f.state.releaseTranscription();await f.flush();assert.deepEqual(f.state.sent,[]);
  assert.equal(f.state.tracks.every(t=>t.stopped),true);f.voice.end();
});

test('permission granted after pause releases the late microphone without starting a recorder',async()=>{
  const f=fixture({holdMic:true});await f.start();assert.equal(f.state.tracks.length,1);
  f.voice.pause();f.state.releaseMic();await f.flush();
  assert.equal(f.state.tracks[0].stopped,true);assert.equal(f.state.intervals.size,0);assert.deepEqual(f.state.sent,[]);f.voice.end();
});

test('an old audio completion cannot start listening in a later session',async()=>{
  const f=fixture();await f.start();await f.tick(4,true);await f.tick(13,false);await f.flush();
  const old=f.state.players[0];f.voice.end();await f.start();const before=f.state.tracks.length;
  old.ended();await f.flush();assert.equal(f.state.tracks.length,before);f.voice.end();
});

test('spoken end asks first and closes only after confirmed goodbye playback',async()=>{
  const f=fixture({words:['End the call','yes']});await f.start(true);
  await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.match(f.state.sent[0],/Would you like me to end/);assert.equal(f.voice.isActive(),true);
  f.state.players[0].ended();await f.flush();
  await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.match(f.state.sent[1],/Goodbye/);assert.equal(f.voice.isActive(),true);
  f.state.players[1].ended();await f.flush();
  assert.equal(f.voice.isActive(),false);assert.equal(f.elements['voice-conversation-export'].open,true);
});
test('declining spoken end leaves the conversation active',async()=>{
  const f=fixture({words:['End the call','no']});await f.start();
  await f.tick(4,true);await f.tick(13,false);await f.flush();
  f.state.players[0].ended();await f.flush();
  await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.match(f.state.sent[1],/keep talking/);
  f.state.players[1].ended();await f.flush();assert.equal(f.voice.isActive(),true);f.voice.end();
});

for (const phrase of ["Hang up", "Stop voice chat", "Let's finish our conversation", "I'd like to end the conversation now.", "I’d like to end the conversation now.", 'It is time to end the conversation. Goodbye.', "Goodbye, let's end the conversation now."]) {
  test('natural end request needs confirmation: '+phrase,async()=>{
    const f=fixture({words:[phrase,'yes']});await f.start();
    await f.tick(4,true);await f.tick(13,false);await f.flush();
    assert.match(f.state.sent[0],/Would you like me to end/);assert.equal(f.voice.isActive(),true);
    f.state.players[0].ended();await f.flush();
    await f.tick(4,true);await f.tick(13,false);await f.flush();
    f.state.players[1].ended();await f.flush();assert.equal(f.voice.isActive(),false);
  });
}

test('screen wake lock follows start, pause, resume and end',async()=>{
  const f=fixture({wakeLock:true});await f.start();await f.flush();
  assert.equal(f.state.wakeRequests,1);
  f.voice.pause();await f.flush();assert.equal(f.state.wakeReleases,1);
  await f.elements['voice-session-pause'].onclick();await f.flush();assert.equal(f.state.wakeRequests,2);
  f.voice.end();await f.flush();assert.equal(f.state.wakeReleases,2);
});

for (const answer of ['Yes, please hang up.', 'Yes I do.', 'Yeah go ahead.', 'Okay, end the call.']) {
 test('natural confirmation: '+answer,async()=>{
  const f=fixture({words:['Hang up please hang up',answer]});await f.start();
  await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.match(f.state.sent[0],/Would you like me to end/);
  f.state.players[0].ended();await f.flush();
  await f.tick(4,true);await f.tick(13,false);await f.flush();
  assert.match(f.state.sent[1],/Goodbye/);
  f.state.players[1].ended();await f.flush();assert.equal(f.voice.isActive(),false);
 });
}
