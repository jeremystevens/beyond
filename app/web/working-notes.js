window.BeyondWorkingNotes = (() => {
 function init({getChatId,isBusy}){
  const $=id=>document.getElementById('notes-'+id);
  let chat=null,controller=null,serial=0,state=null,dirty=false;
  function controls(){
   const busy=!!controller;$('text').disabled=busy;
   $('draft').disabled=busy||isBusy()||!state;$('save').disabled=busy||!state||!$('text').value.trim();
   $('pause').disabled=busy||!state?.enabled;$('clear').disabled=busy||!state?.revision;
   $('count').textContent=$('text').value.length+' / 1,600';
  }
  function cancel(){serial++;controller?.abort();controller=null;controls();}
  function changed(){
   const next=getChatId();$('open').disabled=!next;
   if(next!==chat){cancel();chat=next;state=null;$('dialog').close();$('text').value='';dirty=false;}
   controls();
  }
  function describe(){
   if(state.invalidated)return 'Notes were cleared because covered chat history changed. Draft or write current notes before using them again.';
   if(!state.text)return 'No working notes yet. Write notes yourself or draft them from this conversation.';
   return (state.enabled?'Notes are in use for this chat. ':'Saved notes are paused. ')+
    (state.new_messages?state.new_messages+' newer messages are not included. Update notes when useful; newer chat messages take precedence.':'Notes cover the conversation as last saved.');
  }
  async function request(path,method='GET',body){
   const response=await fetch(path,{method,signal:controller.signal,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
   const data=await response.json().catch(()=>({}));if(!response.ok)throw Error(data.error||'Working notes are unavailable.');return data;
  }
  async function perform(action){
   if(controller||!getChatId())return;
   if(action==='draft'&&dirty&&!confirm('Replace your unsaved edits with a fresh draft?'))return;
   if(action==='clear'&&!confirm('Clear these working notes? Chat messages and global memories will be kept.'))return;
   const id=getChatId(),mine=++serial;controller=new AbortController();controls();
   $('status').textContent=action==='draft'?'Drafting notes… Review before using them.':'Updating working notes…';
   const timeout=setTimeout(()=>controller?.abort(),140000);
   try{
    const base=`/api/chats/${id}/working-notes`;
    let data;
    if(action==='open')data=await request(base);
    if(action==='draft')data=await request(base+'/draft','POST');
    if(action==='save')data=await request(base,'PUT',{text:$('text').value,enabled:true,revision:state.revision,fingerprint:state.fingerprint});
    if(action==='pause'||action==='clear')data=await request(base+'/pause','POST',{revision:state.revision,clear:action==='clear'});
    if(mine!==serial||id!==getChatId())return;
    if(action==='draft'){
     $('text').value=data.text;state.fingerprint=data.fingerprint;dirty=true;
     $('status').textContent='Draft only—review and edit, then Save and use. '+(data.partial?'Selected excerpts from '+data.used_messages+' of '+data.total_messages+' messages; older details may be missing.':'Covers '+data.total_messages+' conversation messages.');
    }else{
     state=data;
     if(action!=='pause'){$('text').value=data.text;dirty=false;}
     $('status').textContent=describe();
    }
   }catch(error){if(mine===serial)$('status').textContent=error.name==='AbortError'?'Cancelled or timed out. Saved notes were not replaced by a draft.':error.message;}
   finally{clearTimeout(timeout);if(mine===serial){controller=null;controls();}}
  }
  $('open').onclick=()=>{changed();if(!getChatId())return;$('dialog').showModal();perform('open');};
  for(const action of ['draft','save','pause','clear'])$(action).onclick=()=>perform(action);
  $('close').onclick=()=>$('dialog').close();$('dialog').addEventListener('close',cancel);
  $('text').addEventListener('input',()=>{dirty=true;controls();});
  changed();return {changed};
 }
 return {init};
})();
