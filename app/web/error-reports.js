window.BeyondErrorReports = (() => {
  const $ = name => document.getElementById('report-'+name);
  let simulated=false;
  let selected=null, controller=null, serial=0, filename='beyond-error-report.txt';
  function cancel(){serial++;controller?.abort();controller=null;$('build').disabled=false;}
  function resetGitHub(){ $('github-results').replaceChildren();$('github-next').hidden=true;$('github').disabled=true; }
  function invalidate(){cancel();resetGitHub();$('copy').disabled=$('save').disabled=true;$('status').textContent='Details changed. Build a new preview before exporting.';}
  function open(id,source){
    cancel();resetGitHub();selected=id;filename='beyond-error-report-'+id+'.txt';
    for(const name of ['happened','expected','steps','tried','preview'])$(name).value='';
    $('environment').checked=true;$('copy').disabled=$('save').disabled=true;
    $('title').textContent='Error report · '+source;
    $('status').textContent='Add any useful details, then build a local preview. Nothing is submitted.';
    $('dialog').showModal();$('happened').focus();
  }
  async function build(){
    if(controller||!selected)return;
    resetGitHub();
    const mine=++serial;controller=new AbortController();$('build').disabled=true;
    $('copy').disabled=$('save').disabled=true;$('status').textContent='Preparing local report…';
    const notes=Object.fromEntries(['happened','expected','steps','tried'].map(n=>[n,$(n).value]));
    notes.include_environment=$('environment').checked;
    try{
      const r=await fetch('/api/status/errors/'+selected+'/report',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(notes),signal:controller.signal});
      const data=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:data.error||'The report could not be prepared.');
      if(mine!==serial)return;
      $('preview').value=data.text;filename=data.filename;simulated=!!data.simulated;
      $('github').disabled=simulated;
      $('occurrences').textContent=data.occurrences ? `Same summary recorded ${data.occurrences.count} time(s) in retained local history; this may have different causes.` : '';
      $('copy').disabled=$('save').disabled=false;
      $('status').textContent=(data.simulated?'SIMULATED TEST. ':'')+'Preview ready. Review and edit it; Copy and Save export exactly this text. Redaction is best effort.';
    }catch(e){if(mine===serial)$('status').textContent=e.name==='AbortError'?'Cancelled.':e.message||'BEYOND is not responding.';}
    finally{if(mine===serial){controller=null;$('build').disabled=false;}}
  }
  async function checkGitHub(){
    if(controller||!selected||simulated)return;
    const mine=++serial;controller=new AbortController();$('github').disabled=true;$('github-next').hidden=true;
    $('status').textContent='Checking GitHub for possible duplicates. Only the error category and a report reference are sent to the search API.';
    try{
      const r=await fetch('/api/status/errors/'+selected+'/github/check',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text:$('preview').value}),signal:controller.signal});
      const data=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'GitHub could not be checked.');
      if(mine!==serial)return;
      $('github-results').replaceChildren();
      for(const match of data.matches||[]){
        const link=document.createElement('a');link.href=match.url;link.target='_blank';link.rel='noopener noreferrer';
        link.textContent=`#${match.number} · ${match.state} · ${match.title} (${match.match})`;
        const row=document.createElement('p');row.append(link);$('github-results').append(row);
      }
      $('status').textContent=data.note+(data.needs_paste?' This report is too long for a prefilled link: Copy report, continue on GitHub, then paste it.':'');
      $('github-next').href=data.draft_url;$('github-next').hidden=false;
    }catch(e){if(mine===serial)$('status').textContent=e.message||'GitHub could not be checked.';}
    finally{if(mine===serial){controller=null;$('github').disabled=simulated;}}
  }
  function init(){
    for(const name of ['happened','expected','steps','tried'])$(name).addEventListener('input',invalidate);
    $('environment').addEventListener('change',invalidate);
    $('build').onclick=build;
    $('github').onclick=checkGitHub;
    $('preview').addEventListener('input',()=>{cancel();resetGitHub();$('github').disabled=simulated||$('copy').disabled;$('status').textContent='Preview changed. Check GitHub again before continuing there.';});
    $('close').onclick=()=>$('dialog').close();$('dialog').addEventListener('close',cancel);
    $('copy').onclick=async()=>{
      try{
        try{if(!navigator.clipboard||!isSecureContext)throw new Error();await navigator.clipboard.writeText($('preview').value);}
        catch{$('preview').focus();$('preview').select();if(!document.execCommand('copy'))throw new Error();}
        $('status').textContent='Report copied. Nothing was submitted.';
      }catch{$('status').textContent='Select the preview and copy it manually.';}
    };
    $('save').onclick=()=>{
      const url=URL.createObjectURL(new Blob([$('preview').value],{type:'text/plain;charset=utf-8'}));
      const a=document.createElement('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();
      setTimeout(()=>URL.revokeObjectURL(url),10000);
      $('status').textContent='Download requested. Your browser chooses the save location. Nothing was submitted.';
    };
  }
  document.addEventListener('DOMContentLoaded',init);
  return {open};
})();
