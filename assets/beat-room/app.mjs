import {CATEGORIES,GROOVES,TRACKS,KITS,byId,meterOf,makeState,patternFor,stepDuration,migrate,clone} from './grooves.mjs';
import {createEngine,hit,scheduleStep,renderBeat,encodeWav} from './engine.mjs';

const $=id=>document.getElementById(id),STORE='malosound-beat-room-v2',FAVORITES='malosound-groove-favorites-v1';
const tell=(message,error=false)=>{ $('status').textContent=message; $('status').dataset.tone=error?'error':'normal'; };
let state=makeState(),favorites=new Set(),filter='all',recovered=false;
try{const raw=localStorage.getItem(STORE)||localStorage.getItem('malosound-beat-room-v1');if(raw){state=migrate(JSON.parse(raw));recovered=true;}}catch{tell('Your previous sketch could not be loaded. Its saved data has not been deleted.',true);}
try{const saved=JSON.parse(localStorage.getItem(FAVORITES));if(Array.isArray(saved))favorites=new Set(saved.filter(id=>byId(id)));}catch{}
let pattern=patternFor(state),page=0,gridSteps=0,pads=[],trackRows={},muteButtons={},volumeInputs={};
let audio=null,engine=null,playing=false,starting=false,nextTime=0,nextIndex=0,nextCycle=0,timer=0,queue=[],painted=-1,paintedCycle=0;
let recording=false,requestingMic=false,finishing=false,exporting=false,recorder=null,micStream=null,micNode=null,micGain=null,analyser=null,recordDest=null,recordStart=0,recordTimer=0,takeCount=0;
const undo=[],heldNodes=new Set(),takeUrls=new Set();
const busy=()=>recording||requestingMic||finishing;
const saveLocal=()=>{try{localStorage.setItem(STORE,JSON.stringify(state));localStorage.setItem(FAVORITES,JSON.stringify([...favorites]));}catch{tell('Browser storage is unavailable. Use Save sketch to keep your work.',true);}};
const remember=()=>{undo.push(clone(state));if(undo.length>40)undo.shift();};
const midiName=midi=>['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][midi%12];
const trackLabel=id=>id==='perc'?({rim:'Rim',conga:'Conga',bongo:'Bongo'}[byId(state.groove).perc]):id==='shaker'?({guira:'Guira',guiro:'Guiro',shaker:'Shaker'}[byId(state.groove).texture]):TRACKS.find(t=>t[0]===id)[1];

function renderFilters(){
  const el=$('genre-filters');el.replaceChildren();
  for(const [id,name] of [['all','All grooves'],...CATEGORIES,['favorites','Favorites']]){const b=document.createElement('button');b.className='filter';b.dataset.category=id;b.dataset.edit='';b.disabled=busy();b.textContent=name;b.setAttribute('aria-pressed',String(filter===id));b.addEventListener('click',()=>{if(busy())return;filter=id;const first=GROOVES.find(g=>g.category===id);if(first&&byId(state.groove).category!==id)loadGroove(first.id,{reveal:false});renderFilters();renderLibrary();el.querySelector(`[data-category="${id}"]`)?.focus();});el.append(b);}
}
function renderLibrary(){
  let loaded=$('library-loaded');
  if(!loaded){loaded=document.createElement('p');loaded.id='library-loaded';loaded.className='library-loaded';$('genre-filters').before(loaded);}
  loaded.textContent=`Loaded: ${byId(state.groove).name} / ${state.bpm} BPM / ${byId(state.groove).meter} / ${KITS[state.kit]}`;
  const container=$('groove-library');container.replaceChildren();
  for(const [id,name] of CATEGORIES){
    const grooves=GROOVES.filter(g=>g.category===id&&(filter==='all'||filter===id||(filter==='favorites'&&favorites.has(g.id))));if(!grooves.length)continue;
    const section=document.createElement('section');section.className='groove-section';const heading=document.createElement('h2');heading.textContent=name;section.append(heading);
    const cards=document.createElement('div');cards.className='groove-cards';
    for(const g of grooves){
      const card=document.createElement('article');card.className='groove-card'+(g.id===state.groove?' is-selected':'');card.dataset.groove=g.id;
      const title=document.createElement('h3');title.textContent=g.name;const text=document.createElement('p');text.textContent=g.description;
      const meta=document.createElement('div');meta.className='groove-meta';meta.textContent=g.id===state.groove?`Loaded / ${state.bpm} BPM / ${g.meter} / ${KITS[state.kit]}`:`${g.bpm} BPM / ${g.meter} / ${KITS[g.kit]}`;
      const actions=document.createElement('div');actions.className='groove-actions';
      const load=document.createElement('button');load.dataset.edit='';load.className='load-groove';load.textContent='Load beat';load.setAttribute('aria-label','Load beat: '+g.name);load.disabled=busy();load.addEventListener('click',()=>loadGroove(g.id));
      const fav=document.createElement('button');fav.className='favorite';fav.dataset.favorite=g.id;fav.textContent=favorites.has(g.id)?'Favorited':'Favorite';fav.setAttribute('aria-label',(favorites.has(g.id)?'Remove favorite ':'Favorite ')+g.name);fav.setAttribute('aria-pressed',String(favorites.has(g.id)));fav.addEventListener('click',()=>{if(favorites.has(g.id))favorites.delete(g.id);else favorites.add(g.id);saveLocal();renderLibrary();(container.querySelector(`[data-favorite="${g.id}"]`)||$('genre-filters').querySelector('[aria-pressed="true"]'))?.focus();});
      actions.append(load,fav);card.append(title,text,meta,actions);cards.append(card);
    }section.append(cards);container.append(section);
  }
  if(!container.children.length){const p=document.createElement('p');p.className='empty-favorites';p.textContent='Save a groove to find it here. Favorites stay in this browser.';container.append(p);}
  $('library-count').textContent=`24 grooves / ${favorites.size} favorites`;
}
function loadGroove(id,{reveal=true}={}){
  if(busy())return;const resume=playing;remember();if(playing)stopBeat();const next=makeState(id);next.words=state.words;next.level=state.level;state=next;page=0;refresh();saveLocal();renderLibrary();if(reveal){$('library').open=false;$('workspace').scrollIntoView({block:'start',behavior:'auto'});$('play').focus();}if(resume)startBeat();tell(`${byId(id).name} loaded. ${state.bpm} BPM / ${byId(id).meter}.`);
}
function rebuildGrid(){
  const m=meterOf(state);if(gridSteps===m.steps&&pads.length)return;gridSteps=m.steps;pads=[];trackRows={};muteButtons={};volumeInputs={};
  const container=$('sequencer');container.replaceChildren();container.style.setProperty('--steps',m.steps);
  const head=document.createElement('div');head.className='step-head';head.setAttribute('aria-hidden','true');head.append(document.createElement('span'));
  for(let i=0;i<m.steps;i++){const s=document.createElement('span');s.textContent=i%m.stepsPerBeat===0?String(i/m.stepsPerBeat+1):'.';if(i%m.stepsPerBeat===0)s.className='beat-number';head.append(s);}container.append(head);
  TRACKS.forEach(([id,,tone],row)=>{
    const line=document.createElement('div');line.className='track';line.style.setProperty('--tone',tone);line.setAttribute('role','group');trackRows[id]=line;
    const controls=document.createElement('div');controls.className='track-controls';const mute=document.createElement('button');mute.className='track-name';mute.dataset.edit='';muteButtons[id]=mute;
    mute.addEventListener('click',()=>{remember();state.muted=state.muted.includes(id)?state.muted.filter(x=>x!==id):[...state.muted,id];refresh();saveLocal();});
    const volume=document.createElement('input');volume.type='range';volume.min='0';volume.max='100';volume.dataset.edit='';volumeInputs[id]=volume;
    volume.addEventListener('input',()=>{state.volumes[id]=Number(volume.value)/100;saveLocal();});controls.append(mute,volume);line.append(controls);
    for(let step=0;step<m.steps;step++){
      const pad=document.createElement('button');pad.className='pad'+(step%m.stepsPerBeat===0?' beat-start':'');pad.dataset.edit='';pad.tabIndex=row===0&&step===0?0:-1;pad.dataset.row=row;pad.dataset.step=step;
      pad.addEventListener('focus',()=>pads.forEach(p=>p.tabIndex=p===pad?0:-1));
      pad.addEventListener('keydown',e=>{const moves={ArrowRight:1,ArrowLeft:-1,ArrowDown:gridSteps,ArrowUp:-gridSteps};if(e.key in moves){e.preventDefault();pads[(row*gridSteps+step+moves[e.key]+pads.length)%pads.length].focus();}});
      pad.addEventListener('click',async e=>{
        if(busy())return;remember();const index=page*gridSteps+step,old=pattern[id][index];state.edits[id]??={};
        if(id==='bass'){const notes=[null,0,2,3,5,7,10,12],next=notes[(notes.indexOf(old?.n??null)+1)%notes.length];state.edits[id][index]=next===null?null:{n:next,v:.75};}
        else if(e.shiftKey&&old){state.edits[id][index]={v:old.v<.5?.65:old.v<.8?.95:.35};}else state.edits[id][index]=old?null:{v:.8};
        refresh();saveLocal();const cell=pattern[id][index];if(!playing&&cell&&!state.muted.includes(id)&&(id!=='bass'||state.bassEnabled)&&(!['perc','shaker'].includes(id)||state.percussion)){try{await ready();hit(engine,{id,n:cell.n??0,velocity:cell.v*state.volumes[id],index},audio.currentTime+.02,state,heldNodes);}catch(error){tell(error.message,true);}}
      });line.append(pad);pads.push(pad);
    }container.append(line);
  });
}
function refresh(){
  pattern=patternFor(state);rebuildGrid();const g=byId(state.groove),m=meterOf(state);
  $('groove-name').textContent=g.name;$('groove-category').textContent=CATEGORIES.find(c=>c[0]===g.category)[1];$('meter').textContent=g.meter+' / two bars';$('bpm').title='BPM counts the '+m.unit;
  $('bpm').value=state.bpm;$('swing').value=Math.round(state.swing*100);$('swing-value').textContent=Math.round(state.swing*100)+'%';$('human').value=Math.round(state.human*100);$('human-value').textContent=Math.round(state.human*100)+'%';$('complexity').value=state.complexity;$('complexity-value').textContent=state.complexity+'%';
  $('variation').value=state.variation;$('kit').value=state.kit;$('bass-sound').value=state.bassSound;$('bass-enabled').checked=state.bassEnabled;$('percussion').checked=state.percussion;$('root').value=state.root;$('level').value=Math.round(state.level*100);$('words').value=state.words;
  document.querySelectorAll('[data-bar]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.bar)===page)));
  TRACKS.forEach(([id],row)=>{const name=trackLabel(id),enabled=!state.muted.includes(id);muteButtons[id].textContent=name;muteButtons[id].setAttribute('aria-label',name+' enabled');muteButtons[id].setAttribute('aria-pressed',String(enabled));volumeInputs[id].value=Math.round(state.volumes[id]*100);volumeInputs[id].setAttribute('aria-label',name+' volume');trackRows[id].setAttribute('aria-label',name);trackRows[id].classList.toggle('is-muted',!enabled||(id==='bass'&&!state.bassEnabled)||(['perc','shaker'].includes(id)&&!state.percussion));
    for(let step=0;step<m.steps;step++){const cell=pattern[id][page*m.steps+step],pad=pads[row*m.steps+step];pad.setAttribute('aria-pressed',String(!!cell));pad.style.setProperty('--velocity',cell?.v??0);pad.textContent=id==='bass'&&cell?midiName(state.root+cell.n):'';pad.setAttribute('aria-label',`${name}, bar ${page+1}, step ${step+1}, ${cell?(id==='bass'?midiName(state.root+cell.n):'on'):'off'}`);}
  });paint(painted,paintedCycle,true);lock();
}
function lock(){document.querySelectorAll('[data-edit]').forEach(el=>el.disabled=busy());$('undo').disabled=busy()||!undo.length;$('play').disabled=busy()||starting;$('record').disabled=requestingMic||finishing||exporting;$('export').disabled=busy()||exporting;$('open').disabled=busy();$('file').disabled=busy();}
async function ready(){
  if(!audio){const AC=window.AudioContext||window.webkitAudioContext;if(!AC)throw new Error('This browser does not support Web Audio.');audio=new AC();engine=createEngine(audio,state.level);audio.addEventListener('statechange',()=>{if(audio.state==='suspended'&&playing){if(recording)stopTake();else stopBeat();tell('Audio was interrupted. Press play to resume.');}});}
  await audio.resume();if(audio.state!=='running')throw new Error('Audio is paused by the browser. Press play again.');
}
function paint(index,cycle,force=false){
  if(!force&&index===painted&&cycle===paintedCycle)return;painted=index;paintedCycle=cycle;const m=meterOf(state),bar=index<0?0:Math.floor(index/m.steps),beat=index<0?0:Math.floor((index%m.steps)/m.stepsPerBeat);
  pads.forEach(p=>p.classList.toggle('playhead',index>=0&&page===bar&&Number(p.dataset.step)===index%m.steps));document.querySelectorAll('.pulse-display i').forEach((el,i)=>el.classList.toggle('active',index>=0&&i===beat));$('bar').textContent=String(index<0?1:cycle*2+bar+1).padStart(2,'0')+' : '+String(beat+1).padStart(2,'0');
}
function tick(){
  if(!playing)return;const now=audio.currentTime,n=meterOf(state).steps*2;
  if(nextTime<now-.15){while(nextTime<now+.04){nextTime+=stepDuration(state,nextIndex);nextIndex++;if(nextIndex===n){nextIndex=0;nextCycle++;}}queue=[];}
  while(nextTime<now+.16){scheduleStep(engine,state,pattern,nextIndex,nextTime,nextCycle,heldNodes);queue.push({index:nextIndex,cycle:nextCycle,time:nextTime});nextTime+=stepDuration(state,nextIndex);nextIndex++;if(nextIndex===n){nextIndex=0;nextCycle++;}}
  let current;while(queue.length&&queue[0].time<=now)current=queue.shift();if(current)paint(current.index,current.cycle);
}
function startBeat(){
  document.querySelectorAll('.take audio').forEach(a=>a.pause());playing=true;nextTime=audio.currentTime+.07;nextIndex=0;nextCycle=0;queue=[];$('play').setAttribute('aria-pressed','true');$('play').setAttribute('aria-label','Stop beat');$('play').innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6h12v12H6z"/></svg>';tick();timer=setInterval(tick,25);
}
function stopBeat(){
  playing=false;clearInterval(timer);queue=[];heldNodes.forEach(n=>{try{n.stop();}catch{}});heldNodes.clear();if(engine){engine.openVoices=[];engine.bassVoices=[];}paint(-1,0);$('play').setAttribute('aria-pressed','false');$('play').setAttribute('aria-label','Play beat');$('play').innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4v16l14-8z"/></svg>';
}
async function toggleBeat(){if(starting||busy())return;if(playing){stopBeat();return;}starting=true;lock();try{await ready();startBeat();tell('Playing '+byId(state.groove).name+'. Change the groove, kit, or steps while it plays.');}catch(e){tell(e.message,true);}finally{starting=false;lock();}}
const timestamp=seconds=>Math.floor(seconds/60)+':'+String(Math.floor(seconds%60)).padStart(2,'0');
function cleanMic(){clearInterval(recordTimer);if(micStream)micStream.getTracks().forEach(t=>t.stop());if(micNode)micNode.disconnect();if(micGain)micGain.disconnect();if(analyser)analyser.disconnect();if(recordDest){try{engine.output.disconnect(recordDest);}catch{}recordDest.stream.getTracks().forEach(t=>t.stop());}micStream=micNode=micGain=analyser=recordDest=null;$('meter-fill').style.width='0%';}
function recordingUI(){$('record').classList.toggle('is-recording',recording);$('record-label').textContent=requestingMic?'Opening microphone...':finishing?'Saving take...':recording?'Stop take':'Record voice + beat';lock();}
function stopTake(){if(!recording||!recorder)return;recording=false;finishing=true;clearInterval(recordTimer);if(recorder.state!=='inactive')recorder.stop();stopBeat();recordingUI();}
async function startTake(){
  if(requestingMic||finishing||exporting)return;if(recording){stopTake();return;}
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){tell('Recording needs a supported browser on localhost or HTTPS. The beat maker still works.',true);return;}
  requestingMic=true;recordingUI();
  try{
    await ready();micStream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false},video:false});await audio.resume();if(playing)stopBeat();
    recordDest=audio.createMediaStreamDestination();engine.output.connect(recordDest);micNode=audio.createMediaStreamSource(micStream);micGain=audio.createGain();micGain.gain.value=Number($('mic-level').value)/100;analyser=audio.createAnalyser();analyser.fftSize=256;micNode.connect(micGain);micGain.connect(recordDest);micGain.connect(analyser);
    const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(x=>MediaRecorder.isTypeSupported(x));recorder=new MediaRecorder(recordDest.stream,mime?{mimeType:mime}:undefined);const chunks=[],began=new Date();let failed=false;
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onerror=()=>{failed=true;tell('Recording stopped with a browser error. Any available audio will appear as a partial take.',true);if(recording)stopTake();};
    recorder.onstop=()=>{
      const type=recorder.mimeType||mime||'audio/webm',blob=new Blob(chunks,{type});cleanMic();recording=false;finishing=false;requestingMic=false;recordingUI();
      if(blob.size){const url=URL.createObjectURL(blob);takeUrls.add(url);takeCount++;const card=document.createElement('div');card.className='take';const head=document.createElement('div');head.className='take-head';const title=document.createElement('span');title.textContent=(failed?'Partial take ':'Take ')+String(takeCount).padStart(2,'0');const remove=document.createElement('button');remove.className='quiet';remove.textContent='Remove';remove.setAttribute('aria-label','Remove '+title.textContent);head.append(title,remove);const player=document.createElement('audio');player.controls=true;player.preload='metadata';player.src=url;const link=document.createElement('a');link.href=url;link.download='malosound-take-'+began.toISOString().replace(/[:.]/g,'-')+(type.includes('mp4')?'.m4a':type.includes('ogg')?'.ogg':'.webm');link.textContent='Download take';card.append(head,player,link);$('takes').prepend(card);remove.addEventListener('click',()=>{if(!confirm('Remove this take? Download it first if you want to keep it.'))return;player.pause();player.removeAttribute('src');URL.revokeObjectURL(url);takeUrls.delete(url);card.remove();});player.addEventListener('play',()=>{if(recording){player.pause();return;}if(playing)stopBeat();document.querySelectorAll('.take audio').forEach(a=>{if(a!==player)a.pause();});});tell(failed?'A partial take is available to download.':'Take ready. Download it before closing this tab.');}else tell('No audio was captured. Try another take.',true);
    };
    recorder.start(250);requestingMic=false;recording=true;recordStart=audio.currentTime;$('record-clock').textContent='0:00';recordingUI();startBeat();tell('Recording microphone + beat locally. Monitoring is off.');const samples=new Uint8Array(analyser.fftSize);
    recordTimer=setInterval(()=>{if(!recording)return;const elapsed=audio.currentTime-recordStart;$('record-clock').textContent=timestamp(elapsed);analyser.getByteTimeDomainData(samples);let energy=0;for(const n of samples)energy+=((n-128)/128)**2;$('meter-fill').style.width=Math.min(100,Math.sqrt(energy/samples.length)*350)+'%';if(elapsed>=300){stopTake();tell('Five-minute limit reached. Saving your take.');}},100);
    micStream.getAudioTracks().forEach(t=>t.addEventListener('ended',()=>{if(recording){stopTake();tell('Microphone disconnected. Saving the available take.');}}));
  }catch(e){cleanMic();recording=false;requestingMic=false;finishing=false;recordingUI();tell(e.name==='NotAllowedError'?'Microphone permission was not granted. The beat maker still works.':'Could not start recording: '+e.message,true);}
}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
async function exportBeat(){
  if(exporting||busy())return;exporting=true;lock();const oldText=$('export').textContent;$('export').textContent='Rendering WAV...';
  try{const s=clone(state),bars=Number($('length').value),render=await renderBeat(s,bars,window.OfflineAudioContext||window.webkitOfflineAudioContext);download(encodeWav(render.buffer),`malosound-${s.groove}-${s.bpm}bpm-${bars}bars.wav`);tell(`${bars} bars of ${byId(s.groove).meter}, plus a ${render.tail}-second sound tail. WAV ready for your DAW.`);}catch(e){tell('Could not export: '+e.message,true);}finally{exporting=false;$('export').textContent=oldText;lock();}
}

renderFilters();renderLibrary();refresh();
$('play').addEventListener('click',toggleBeat);$('record').addEventListener('click',startTake);$('export').addEventListener('click',exportBeat);
$('browse').addEventListener('click',()=>{renderLibrary();$('library').open=true;$('library').scrollIntoView({block:'start',behavior:'auto'});$('library').querySelector('summary').focus();});
document.querySelectorAll('[data-bar]').forEach(b=>b.addEventListener('click',()=>{page=Number(b.dataset.bar);refresh();}));
$('clear').addEventListener('click',()=>{remember();state.edits={};for(const [id] of TRACKS){state.edits[id]={};for(let i=0;i<meterOf(state).steps*2;i++)state.edits[id][i]=null;}refresh();saveLocal();tell('Both bars cleared. Undo restores your pattern.');});
$('reset-groove').addEventListener('click',()=>{remember();state.edits={};refresh();saveLocal();tell('Manual step edits cleared. Groove and sound settings kept.');});
$('undo').addEventListener('click',()=>{if(!undo.length)return;const resume=playing;if(playing)stopBeat();state=undo.pop();page=0;refresh();renderLibrary();if(engine)engine.output.gain.setTargetAtTime(state.level,audio.currentTime,.02);saveLocal();if(resume)startBeat();});
$('bpm').addEventListener('change',()=>{remember();state.bpm=Math.min(200,Math.max(40,Math.round(Number($('bpm').value)||100)));refresh();saveLocal();});
for(const [id,key,scale] of [['swing','swing',100],['human','human',100],['complexity','complexity',1]]){
  $(id).addEventListener('pointerdown',remember);$(id).addEventListener('keydown',e=>{if(e.key.startsWith('Arrow'))remember();});$(id).addEventListener('input',()=>{state[key]=Number($(id).value)/scale;refresh();saveLocal();});
}
for(const [id,key] of [['variation','variation'],['kit','kit'],['bass-sound','bassSound']])$(id).addEventListener('change',()=>{remember();state[key]=$(id).value;refresh();saveLocal();});
for(const [id,key] of [['bass-enabled','bassEnabled'],['percussion','percussion']])$(id).addEventListener('change',()=>{remember();state[key]=$(id).checked;refresh();saveLocal();});
$('root').addEventListener('change',()=>{remember();state.root=Number($('root').value);refresh();saveLocal();});
$('level').addEventListener('input',()=>{state.level=Number($('level').value)/100;if(engine)engine.output.gain.setTargetAtTime(state.level,audio.currentTime,.02);saveLocal();});
$('mic-level').addEventListener('input',()=>{if(micGain)micGain.gain.setTargetAtTime(Number($('mic-level').value)/100,audio.currentTime,.02);});
$('words').addEventListener('input',()=>{state.words=$('words').value.slice(0,100000);saveLocal();});
$('save').addEventListener('click',()=>download(new Blob([JSON.stringify({...state,favorites:[...favorites]},null,2)+'\n'],{type:'application/json'}),'malosound-sketch.json'));
$('open').addEventListener('click',()=>$('file').click());
$('file').addEventListener('change',async()=>{const file=$('file').files[0];if(!file)return;try{if(file.size>250000)throw new Error('The sketch file is too large.');const raw=JSON.parse(await file.text()),next=migrate(raw);if(busy())throw new Error('Finish your take before opening a sketch.');remember();if(playing)stopBeat();state=next;page=0;if(Array.isArray(raw.favorites))raw.favorites.filter(id=>byId(id)).forEach(id=>favorites.add(id));refresh();renderLibrary();if(engine)engine.output.gain.setTargetAtTime(state.level,audio.currentTime,.02);saveLocal();$('library').open=false;tell('Sketch loaded. Press play when ready.');}catch(e){tell(e.message,true);}finally{$('file').value='';}});
window.addEventListener('keydown',e=>{if(e.code==='Space'&&!e.repeat&&!e.target.closest('button,input,textarea,select,[contenteditable=true],summary,a')){e.preventDefault();toggleBeat();}});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&playing)tick();});
window.addEventListener('beforeunload',e=>{if(recording||requestingMic||takeUrls.size){e.preventDefault();e.returnValue='';}});
window.addEventListener('pagehide',()=>{if(recording)stopTake();else stopBeat();if(micStream)micStream.getTracks().forEach(t=>t.stop());});
if(!window.isSecureContext)$('record').title='Microphone recording requires localhost or HTTPS.';
if(recovered)tell('Your saved sketch is here. Explore the library when you want a new starting point.');
