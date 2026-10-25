window.BeyondComposerTools=(()=>{
 function init(){
  const $=id=>document.getElementById(id),trigger=$('composer-more'),panel=$('composer-tools'),toggle=$('think-mode'),badge=$('think-indicator');
  const key='beyond-think-through';
  try{toggle.checked=localStorage.getItem(key)==='on';}catch{}
  function sync(){badge.hidden=!toggle.checked;try{localStorage.setItem(key,toggle.checked?'on':'off');}catch{}}
  function close(focus=false){panel.hidden=true;trigger.setAttribute('aria-expanded','false');if(focus)trigger.focus();}
  function open(){panel.hidden=false;trigger.setAttribute('aria-expanded','true');panel.querySelector('button:not(:disabled),input:not(:disabled)')?.focus();}
  trigger.onclick=()=>panel.hidden?open():close(true);toggle.onchange=sync;
  badge.onclick=()=>{toggle.checked=false;sync();};
  for(const id of ['attach-photo','mic','writing-open'])$(id).addEventListener('click',()=>queueMicrotask(()=>close()));
  document.addEventListener('pointerdown',event=>{if(!panel.hidden&&!panel.contains(event.target)&&!trigger.contains(event.target))close();});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!panel.hidden){event.preventDefault();event.stopImmediatePropagation();close(true);}},true);
  panel.addEventListener('keydown',event=>{
   if(event.key==='Enter'&&event.target===toggle){event.preventDefault();toggle.checked=!toggle.checked;sync();return;}
   if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
   const choices=[...panel.querySelectorAll('button:not(:disabled),input:not(:disabled)')],index=choices.indexOf(document.activeElement);
   const next=event.key==='Home'?0:event.key==='End'?choices.length-1:(index+(event.key==='ArrowDown'?1:-1)+choices.length)%choices.length;
   event.preventDefault();choices[next]?.focus();
  });
  panel.addEventListener('focusout',event=>{const next=event.relatedTarget;if(next&&!panel.contains(next)&&next!==trigger)close();});
  const mic=$('mic'),voice=$('voice-indicator');
  function showVoice(){const recording=mic.classList.contains('recording'),working=mic.classList.contains('working');
   voice.hidden=!recording&&!working;voice.disabled=working;voice.textContent=recording?'Stop recording':'Transcribing…';}
  new MutationObserver(showVoice).observe(mic,{attributes:true,attributeFilter:['class']});
  voice.onclick=()=>mic.click();showVoice();sync();
  return {enabled:()=>toggle.checked,close};
 }
 return {init};
})();
