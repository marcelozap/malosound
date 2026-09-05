(async()=>{
 const make=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
 try{
 const response=await fetch('content/market-map.json');if(!response.ok)throw new Error();const entries=await response.json();entries.sort((a,b)=>b.id.localeCompare(a.id));
 const select=document.getElementById('date'),orbit=document.getElementById('orbit'),focus=document.getElementById('focus');
 entries.forEach(e=>{const option=make('option',e.date);option.value=e.id;select.append(option);});
 const requested=new URLSearchParams(location.search).get('date');if(entries.some(e=>e.id===requested))select.value=requested;
 const positions=[[27,20],[73,20],[80,50],[73,80],[27,80],[20,50]];
 function render(){const e=entries.find(e=>e.id===select.value);document.getElementById('cutoff').textContent=e.edition+' · '+e.cutoffLabel+' · '+e.marketStatus;document.getElementById('report').href=e.reportUrl;orbit.querySelectorAll('button').forEach(b=>b.remove());
 function choose(t){focus.replaceChildren(make('h2',t.title),make('p',t.metric+' · '+t.value),make('small',t.observation),make('h3',t.headline),make('p',t.mechanism),make('h3','What would change the view'),make('p',t.falsifier));e.sources.filter(s=>t.sourceIds.includes(s.id)).forEach(s=>{const a=make('a',s.label+' ↗');a.href=s.href;a.target='_blank';a.rel='noreferrer';focus.append(a);});orbit.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.id===t.id)));}
 e.topics.forEach((t,i)=>{const b=make('button',t.title);b.className='force';b.dataset.id=t.id;b.style.left=positions[i][0]+'%';b.style.top=positions[i][1]+'%';b.append(make('strong',t.value));b.addEventListener('click',()=>choose(t));orbit.append(b);});choose(e.topics[0]);
 const events=document.getElementById('events');events.replaceChildren();e.events.forEach(event=>{const article=make('article','');article.className='catalyst';article.append(make('h3',event.label),make('p',event.date+' · '+event.time+' · Eastern'));const source=e.sources.find(s=>s.id===event.sourceId);if(source){const a=make('a','Verify the schedule ↗');a.href=source.href;a.target='_blank';a.rel='noreferrer';article.append(a);}events.append(article);});}
 select.addEventListener('change',render);render();
 }catch{document.getElementById('focus').textContent='The market map could not load. Refresh to try again, or open the complete research below.';}
})();
