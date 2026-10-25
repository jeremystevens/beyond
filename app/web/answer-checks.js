window.BeyondAnswerChecks = (() => {
  const $ = id => document.getElementById('check-'+id);
  let selected=null, controller=null, serial=0;
  function cancel(){serial++;controller?.abort();controller=null;$('run').disabled=false;}
  function mode(){
    const value=$('mode').value;
    $('expression-box').hidden=value!=='math';$('query-box').hidden=value!=='web';$('claim-box').hidden=value==='math';
    $('run').textContent=value==='web'?'Search and check':'Check';
    $('notice').textContent=value==='web'?'Only the search query below is sent to public search. Search snippets are evidence to inspect, not proof.':
      value==='math'?'Recalculate an expression with the safe calculator. No AI or network request.':'Use passages from documents attached to this chat. No web search.';
  }
  function invalidate(){cancel();$('result').hidden=true;$('status').textContent='Inputs changed. Run a new check.';}
  async function open(id){
    cancel();selected=id;const mine=++serial;
    $('claim').value='';$('expression').value='';$('query').value='';$('mode').value='math';mode();
    $('result').hidden=true;$('status').textContent='Loading saved answer…';$('run').disabled=true;
    $('dialog').showModal();controller=new AbortController();
    try{
      const response=await fetch(`/api/messages/${id}/check`,{signal:controller.signal});const data=await response.json();
      if(!response.ok)throw Error(data.error||'Could not open this answer.');
      if(mine!==serial)return;
      $('claim').value=data.claim;$('expression').value=data.expression||'';
      $('documents').disabled=!data.has_documents;
      $('status').textContent=data.truncated?'The answer is long. Select a short, specific claim; the rest will not be checked.':'Choose what to check. The original answer stays unchanged.';
      $('run').disabled=false;
    }catch(error){if(mine===serial)$('status').textContent=error.name==='AbortError'?'Cancelled.':error.message;}
    finally{if(mine===serial)controller=null;}
  }
  async function run(){
    if(controller||!selected)return;
    const mine=++serial;controller=new AbortController();$('run').disabled=true;
    $('result').hidden=true;$('status').textContent='Checking… Close to cancel.';
    const timeout=setTimeout(()=>controller?.abort(),140000);
    try{
      const response=await fetch(`/api/messages/${selected}/check`,{method:'POST',headers:{'Content-Type':'application/json'},
        signal:controller.signal,body:JSON.stringify({mode:$('mode').value,claim:$('claim').value,expression:$('expression').value,query:$('query').value})});
      const data=await response.json();if(!response.ok)throw Error(data.error||'The check could not finish.');
      if(mine!==serial)return;
      $('assessment-title').textContent=data.ai_used?'AI assessment of selected evidence':'Check result';
      $('assessment').textContent=data.assessment;$('evidence').textContent=data.evidence;$('limit').textContent=data.limit;
      $('sources').replaceChildren();
      for(const url of data.sources||[]){
        try{const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol))continue;}catch{continue;}
        const link=document.createElement('a');link.href=url;link.textContent=url;link.target='_blank';link.rel='noopener noreferrer';
        const line=document.createElement('p');line.append(link);$('sources').append(line);
      }
      $('result').hidden=false;$('status').textContent=data.method+' · '+new Date(data.at).toLocaleString();
    }catch(error){if(mine===serial)$('status').textContent=error.name==='AbortError'?'Check cancelled or timed out. No conclusion established.':error.message;}
    finally{clearTimeout(timeout);if(mine===serial){controller=null;$('run').disabled=false;}}
  }
  function init(){
    $('mode').onchange=()=>{invalidate();mode();};
    for(const id of ['claim','expression','query'])$(id).addEventListener('input',invalidate);
    $('run').onclick=run;$('close').onclick=()=>$('dialog').close();$('dialog').addEventListener('close',cancel);mode();
  }
  return {init,open,changed(){if($('dialog').open)$('dialog').close();}};
})();
