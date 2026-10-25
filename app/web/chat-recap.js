window.BeyondRecap = (() => {
  function init({getChatId,isBusy}) {
    const $ = id => document.getElementById('recap-'+id);
    let chat = null, controller = null, serial = 0;
    function cancel() { serial++; controller?.abort(); controller=null; $('refresh').disabled=false; }
    function changed() {
      const next=getChatId();
      $('tools').hidden=!next; $('open').disabled=isBusy();
      if(next!==chat){cancel();chat=next;$('dialog').close();$('text').textContent='';$('copy').disabled=true;}
    }
    async function load(refresh=false) {
      if(controller || !getChatId())return;
      const id=getChatId(), mine=++serial;
      controller=new AbortController();$('refresh').disabled=true;
      $('text').textContent='';$('copy').disabled=true;
      $('status').textContent=refresh?'Refreshing recap…':'Opening recap… A new recap can take a moment.';
      try {
        const r=await fetch(`/api/chats/${id}/recap`,{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({refresh}),signal:controller.signal});
        const data=await r.json().catch(()=>({}));
        if(!r.ok)throw new Error(data.error || 'The recap is unavailable. Refresh after updating and restarting BEYOND.');
        if(mine!==serial || id!==getChatId())return;
        $('text').textContent=data.text;$('copy').disabled=false;
        $('status').textContent=(data.cached?'Saved recap reused. ':'New recap created. ')+
          (data.partial?`Selected excerpts from ${data.used_messages} of ${data.total_messages} messages; older details may be missing.`:
           `Covers ${data.total_messages} conversation messages.`)+
          (data.saved?'':' This recap could not be cached; copy it to keep it.');
      }catch(error){
        if(mine===serial)$('status').textContent=error.name==='AbortError'?'Cancelled.':
          error.name==='TypeError'?'BEYOND is not responding. Try again when it is running.':error.message;
      }finally{if(mine===serial){controller=null;$('refresh').disabled=false;}}
    }
    $('open').onclick=()=>{changed();if(!getChatId())return;$('dialog').showModal();load();};
    $('refresh').onclick=()=>load(true);
    $('close').onclick=()=>$('dialog').close();
    $('dialog').addEventListener('close',cancel);
    $('copy').onclick=async()=>{
      const text=$('text').textContent;
      try {
        try {if(!navigator.clipboard || !isSecureContext)throw new Error();await navigator.clipboard.writeText(text);}
        catch {
          const field=document.createElement('textarea');field.value=text;$('dialog').append(field);field.select();
          try{if(!document.execCommand('copy'))throw new Error();}finally{field.remove();}
        }
        $('status').textContent='Recap copied.';
      }catch{$('status').textContent='Select the recap text and copy it manually.';}
    };
    changed();return {changed};
  }
  return {init};
})();
