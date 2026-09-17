// Original songwriting starting points, not transcriptions of commercial songs.
export const CATEGORIES = [
  ['band','Live band / Pop / Rock'],['indie','Indie / Funk / Disco'],
  ['soul','Soul / R&B / Neo-soul'],['hiphop','Hip-hop'],['trap','Trap / 808'],
  ['house','House / Dance'],['latin','Latin'],['roots','Acoustic / Ballad / Regional roots']
];
export const TRACKS = [
  ['kick','Kick','#a28b64'],['snare','Snare','#667caa'],['hat','Closed hat','#42628c'],
  ['open','Open hat','#4d727a'],['perc','Percussion','#8a7784'],['shaker','Shaker','#747f67'],['bass','Bass','#837347']
];
export const KITS = {acoustic:'Acoustic-style',vintage:'Dry vintage',electronic:'Electronic','808':'808-style'};
export const METERS = {
  '4/4':{steps:16,stepsPerBeat:4,beats:4,unit:'quarter note'},
  '3/4':{steps:12,stepsPerBeat:4,beats:3,unit:'quarter note'},
  '2/4':{steps:8,stepsPerBeat:4,beats:2,unit:'quarter note'},
  '6/8':{steps:12,stepsPerBeat:6,beats:2,unit:'dotted quarter'},
  '12/8':{steps:24,stepsPerBeat:6,beats:4,unit:'dotted quarter'}
};
const eighths=(n,v=.55)=>Array.from({length:n/2},(_,i)=>[i*2,i%2?v*.7:v]);
const floor=[0,4,8,12,16,20,24,28], back=[4,12,20,28], off=[2,6,10,14,18,22,26,30];
const g=(id,category,name,bpm,meter,kit,description,pattern,options={})=>({id,category,name,bpm,meter,kit,description,pattern,swing:0,human:.18,bass:false,percussion:false,bassSound:'round',perc:'rim',texture:'shaker',late:0,complexity:45,extras:{},turn:{},...options});
export const GROOVES = [
  g('open-backbeat','band','Open backbeat',100,'4/4','acoustic','A steady pocket for guitar and a melody.',{kick:[0,8,16,22,24],snare:back,hat:eighths(32),bass:[[0,0],[8,7],[16,0],[24,7]]},{extras:{snare:[[11,.23],[27,.25]],kick:[[30,.55]]},turn:{snare:[[29,.48],[31,.6]]}}),
  g('wide-backbeat','band','Half-time space',76,'4/4','acoustic','One broad backbeat; room between the hits.',{kick:[0,10,16,23],snare:[8,24],hat:eighths(32,.47),bass:[[0,0],[16,0]]},{extras:{kick:[[14,.5]],snare:[[22,.2]]},turn:{snare:[[28,.52],[30,.65]]}}),
  g('band-shuffle','band','Rolling shuffle',96,'12/8','acoustic','A triplet pulse, not a straight beat with a new name.',{kick:[0,12,24,36,44],snare:[6,18,30,42],hat:[0,4,6,10,12,16,18,22,24,28,30,34,36,40,42,46],bass:[[0,0],[12,7],[24,0],[36,7]]},{extras:{snare:[[16,.22],[40,.22]]},turn:{snare:[[44,.48],[46,.7]]}}),
  g('offbeat-funk','indie','Offbeat pocket',112,'4/4','vintage','Syncopated kick, clipped hats, space for rhythm guitar.',{kick:[0,7,10,16,22,27],snare:back,hat:eighths(32,.5),perc:[[3,.45],[19,.45]],bass:[[0,0],[7,7],[10,0],[16,0],[22,10],[27,7]]},{bass:true,swing:.06,extras:{snare:[[3,.2],[10,.22],[19,.2],[26,.24]],hat:[[15,.3],[31,.3]]},turn:{kick:[[30,.7]],perc:[[29,.5],[31,.6]]}}),
  g('disco-guitar','indie','Disco guitar',118,'4/4','acoustic','Four on the floor with open-hat lift.',{kick:floor,snare:back,hat:[0,4,8,12,16,20,24,28],open:off,bass:[[2,0],[6,12],[10,7],[14,0],[18,0],[22,12],[26,7],[30,10]]},{bass:true,extras:{shaker:eighths(32,.28)},turn:{snare:[[30,.4],[31,.58]]}}),
  g('indie-skip','indie','Loose indie',104,'4/4','vintage','An uneven kick conversation beneath a simple backbeat.',{kick:[0,6,16,26],snare:back,hat:[0,2,6,8,10,14,16,18,22,24,28,30],perc:[[7,.45],[15,.35],[23,.5]],bass:[[0,0],[10,7],[16,0],[26,3]]},{human:.4,late:.007,extras:{kick:[[15,.48]],hat:[[5,.28],[21,.24]]},turn:{open:[[30,.5]],perc:[[29,.55]]}}),
  g('late-pocket','soul','Behind the pocket',78,'4/4','vintage','A late snare and a light swung pulse.',{kick:[0,7,10,16,23],snare:back,hat:eighths(32,.43),bass:[[0,0],[10,7],[16,0],[26,10]]},{swing:.16,late:.014,human:.35,bass:true,extras:{snare:[[9,.24],[19,.22],[27,.2]]},turn:{kick:[[30,.52]],snare:[[31,.38]]}}),
  g('slow-six','soul','Slow six',58,'6/8','acoustic','Two swaying beats in each bar; leave the top line open.',{kick:[0,12,16],snare:[6,18],hat:eighths(24,.42),bass:[[0,0],[12,7]]},{late:.008,extras:{snare:[[10,.22],[22,.22]],perc:[[4,.32],[16,.32]]},turn:{snare:[[20,.42],[22,.58]]}}),
  g('neo-swing','soul','Soft displacement',86,'4/4','vintage','Small kick surprises and a deeper sixteenth swing.',{kick:[0,5,11,16,22,29],snare:back,hat:[[0,.5],[2,.32],[3,.25],[6,.44],[8,.52],[10,.35],[14,.4],[16,.5],[18,.3],[22,.42],[24,.5],[27,.3],[30,.44]],bass:[[0,0],[11,7],[16,0],[29,10]]},{swing:.27,late:.01,human:.35,bass:true,extras:{snare:[[7,.22],[17,.19],[26,.2]],hat:[[7,.24],[23,.24]]},turn:{perc:[[27,.38],[31,.48]]}}),
  g('boom-bap','hiphop','Dusty backbeat',88,'4/4','vintage','A firm snare with a staggered kick.',{kick:[0,6,10,16,19,26],snare:back,hat:eighths(32,.47),bass:[[0,0],[10,7],[16,0],[26,0]]},{swing:.2,bass:true,extras:{snare:[[11,.24],[27,.25]],kick:[[31,.4]]},turn:{snare:[[30,.4],[31,.55]]}}),
  g('mellow-melodic','hiphop','Room for a melody',72,'4/4','vintage','Sparse drums; bring your own harmony.',{kick:[0,10,16,23],snare:[[4,.8],[12,.7],[20,.8],[28,.73]],hat:[0,4,6,8,12,14,16,20,22,24,28,30],bass:[[0,0],[16,0]]},{swing:.1,late:.01,extras:{perc:[[7,.3],[23,.3]],hat:[[11,.2],[27,.2]]},turn:{kick:[[30,.55]]}}),
  g('lofi-drift','hiphop','Low-key swing',76,'4/4','vintage','Soft accents and a loose, unhurried pocket.',{kick:[[0,.8],[7,.6],[16,.78],[25,.64]],snare:[[4,.65],[12,.57],[20,.65],[28,.57]],hat:eighths(32,.36),perc:[[14,.32],[30,.32]],bass:[[0,0],[12,7],[16,0],[28,3]]},{swing:.32,human:.55,late:.012,bass:true,extras:{snare:[[9,.2],[23,.18]],hat:[[3,.18],[19,.18]]},turn:{perc:[[29,.35],[31,.3]]}}),
  g('trap-wide','trap','Wide half-time',142,'4/4','808','A half-time clap, open space, optional sub.',{kick:[0,7,11,16,22,27],snare:[8,24],hat:eighths(32,.4),open:[[14,.35],[30,.38]],bass:[[0,0],[7,0],[11,7],[16,0],[27,10]]},{bass:true,bassSound:'808',human:.06,extras:{hat:[[15,.3],[23,.28],[31,.32]]},rolls:[15,31],turn:{snare:[[30,.38]],kick:[[31,.6]]}}),
  g('trap-hats','trap','Hat conversation',136,'4/4','808','Short hat answers around a spacious backbeat.',{kick:[0,6,15,18,27],snare:[8,24],hat:[0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30],perc:[[11,.4],[29,.43]],bass:[[0,0],[6,3],[15,0],[18,7],[27,0]]},{bass:true,bassSound:'808',human:.07,complexity:65,rolls:[7,15,23,31],extras:{hat:[[5,.24],[21,.22]],perc:[[19,.25]]},turn:{open:[[30,.4]],kick:[[31,.45]]}}),
  g('trap-minimal','trap','Sub and silence',124,'4/4','808','Few drums, long bass, plenty of vocal room.',{kick:[0,14,16,25],snare:[8,24],hat:[0,4,8,12,16,20,24,28],bass:[[0,0],[14,7],[16,0],[25,0]]},{bass:true,bassSound:'808',human:.04,extras:{hat:[[7,.25],[23,.25]],perc:[[30,.3]]},turn:{kick:[[31,.5]],hat:[[30,.32]]}}),
  g('deep-floor','house','Deep floor',122,'4/4','electronic','A steady kick with restrained offbeat lift.',{kick:floor,snare:[[4,.6],[12,.65],[20,.6],[28,.65]],hat:off,open:[[14,.36],[30,.4]],bass:[[2,0],[6,0],[10,7],[14,0],[18,0],[22,3],[26,7],[30,0]]},{bass:true,extras:{hat:[[3,.22],[11,.22],[19,.22],[27,.22]]},turn:{snare:[[30,.38],[31,.46]]}}),
  g('soulful-house','house','Soulful step',118,'4/4','acoustic','Light congas and a swung floor pulse.',{kick:floor,snare:back,hat:off,perc:[[3,.48],[7,.65],[10,.38],[15,.66],[19,.48],[23,.64],[26,.38],[31,.7]],shaker:eighths(32,.24),bass:[[2,0],[7,7],[10,0],[14,10],[18,0],[23,7],[26,0],[30,3]]},{percussion:true,bass:true,perc:'conga',swing:.1,extras:{open:[[14,.3],[30,.3]]},turn:{perc:[[28,.35],[29,.48]]}}),
  g('disco-house','house','Disco drive',126,'4/4','electronic','An open-hat pulse with a short, bouncing bass.',{kick:floor,snare:back,hat:[0,4,8,12,16,20,24,28],open:off,shaker:eighths(32,.26),perc:[[7,.44],[15,.5],[23,.44],[31,.5]],bass:[[0,0],[3,12],[6,7],[10,0],[14,10],[16,0],[19,12],[22,7],[26,0],[30,7]]},{percussion:true,bass:true,extras:{hat:[[5,.2],[13,.2],[21,.2],[29,.2]]},turn:{snare:[[29,.33],[30,.46],[31,.6]]}}),
  g('reggaeton','latin','Reggaeton / dembow',94,'4/4','electronic','Syncopated rim accents against a grounded kick.',{kick:floor,snare:[3,6,11,14,19,22,27,30],hat:off,perc:[[7,.5],[15,.6],[23,.5],[31,.6]],bass:[[0,0],[6,0],[8,7],[14,0],[16,0],[22,0],[24,7],[30,0]]},{percussion:true,bass:true,perc:'conga',extras:{shaker:eighths(32,.24)},turn:{perc:[[28,.4],[29,.5]]}}),
  g('bachata','latin','Bachata / guitar space',124,'4/4','acoustic','Bongo motion and a scraped pulse, not a dembow.',{kick:[[0,.45],[8,.38],[16,.45],[24,.38]],perc:[[0,.55],[2,.42],[4,.65],[6,.4],[8,.55],[10,.42],[12,.62],[14,.9],[16,.55],[18,.42],[20,.65],[22,.4],[24,.55],[26,.42],[28,.62],[30,.9]],shaker:eighths(32,.4),bass:[[0,0],[4,7],[8,0],[12,7],[16,0],[20,7],[24,0],[28,7]]},{percussion:true,perc:'bongo',texture:'guira',extras:{perc:[[13,.3],[29,.3]]},turn:{perc:[[28,.65],[29,.4],[30,.85],[31,.4]]}}),
  g('cumbia','latin','Cumbia / rolling pulse',98,'4/4','vintage','Low drum on the ground; guiro and hand-drum answers.',{kick:[0,8,16,24],hat:[[4,.4],[12,.4],[20,.4],[28,.4]],perc:[[2,.6],[6,.85],[10,.58],[14,.8],[18,.6],[22,.85],[26,.58],[30,.8]],shaker:[[0,.6],[2,.3],[4,.55],[6,.3],[8,.6],[10,.3],[12,.55],[14,.3],[16,.6],[18,.3],[20,.55],[22,.3],[24,.6],[26,.3],[28,.55],[30,.3]],bass:[[0,0],[6,7],[8,0],[14,7],[16,0],[22,7],[24,0],[30,7]]},{percussion:true,bass:true,perc:'conga',texture:'guiro',extras:{perc:[[7,.25],[23,.25]]},turn:{perc:[[27,.35],[31,.55]]}}),
  g('brush-waltz','roots','Brushed ballad',68,'3/4','acoustic','A soft three-beat bed for an acoustic song.',{kick:[[0,.55],[12,.55]],snare:[[4,.4],[8,.34],[16,.4],[20,.34]],shaker:eighths(24,.24),bass:[[0,0],[8,7],[12,0],[20,7]]},{percussion:true,brush:true,human:.35,extras:{perc:[[10,.2],[22,.2]]},turn:{snare:[[22,.27]]}}),
  g('corrido-duple','roots','Corrido-inspired / two',108,'2/4','vintage','An alternating two-beat foundation for guitar.',{kick:[0,8],snare:[[4,.52],[12,.55]],shaker:[[0,.3],[2,.22],[4,.36],[6,.22],[8,.3],[10,.22],[12,.36],[14,.22]],bass:[[0,0],[4,7],[8,0],[12,7]]},{percussion:true,crossstick:true,extras:{perc:[[6,.27],[14,.3]]},turn:{snare:[[14,.3],[15,.35]]}}),
  g('corrido-three','roots','Corrido-inspired / three',96,'3/4','vintage','A root-and-fifth waltz framework, kept light.',{kick:[0,12],snare:[[4,.45],[8,.55],[16,.45],[20,.55]],shaker:[[0,.3],[4,.23],[8,.3],[12,.3],[16,.23],[20,.3]],bass:[[0,0],[4,7],[8,7],[12,0],[16,7],[20,7]]},{percussion:true,crossstick:true,extras:{perc:[[10,.23],[22,.23]]},turn:{snare:[[22,.3]]}})
];
export const byId=id=>GROOVES.find(groove=>groove.id===id);
export const meterOf=s=>METERS[byId(s.groove).meter];
export const clone=x=>JSON.parse(JSON.stringify(x));
export function makeState(id='open-backbeat'){
  const p=byId(id);if(!p)throw new Error('Unknown groove.');
  return {version:2,groove:id,bpm:p.bpm,swing:p.swing,human:p.human,complexity:p.complexity,variation:'main',kit:p.kit,root:33,level:.72,bassSound:p.bassSound,bassEnabled:p.bass,percussion:p.percussion,muted:[],volumes:{kick:.85,snare:.75,hat:.65,open:.55,perc:.65,shaker:.55,bass:.6},edits:{},words:''};
}
export function patternFor(s){
  const p=byId(s.groove),m=meterOf(s),n=m.steps*2;
  const pattern=Object.fromEntries(TRACKS.map(([id])=>[id,Array(n).fill(null)]));
  const add=(map,scale=1)=>Object.entries(map).forEach(([id,events])=>events.forEach(item=>{
    const index=Array.isArray(item)?item[0]:item;
    if(index<0||index>=n)return;
    pattern[id][index]=id==='bass'?{n:Array.isArray(item)?item[1]:0,v:.75*scale}:{v:(Array.isArray(item)?item[1]:.85)*scale};
  }));
  add(p.pattern);
  // Complexity changes lower-priority ornaments, not the defining pulse.
  if(s.complexity<35)for(const [id,cells] of Object.entries(pattern))cells.forEach((cell,i)=>{if(cell&&id!=='bass'&&cell.v<.46&&i%m.stepsPerBeat!==0)cells[i]=null;});
  if(s.complexity>=40)add(p.extras, .65+(s.complexity-40)/170);
  if(s.complexity>=75){const h=pattern.hat;for(let bar=0;bar<2;bar++){const i=bar*m.steps+m.steps-1;if(!h[i])h[i]={v:.24};}}
  if(s.variation==='open')for(const [id,cells] of Object.entries(pattern))cells.forEach((cell,i)=>{if(cell&&((id==='hat'&&i%m.stepsPerBeat!==0)||(id==='snare'&&cell.v<.35)||(id==='perc'&&cell.v<.6)||(id==='shaker'&&i%m.stepsPerBeat!==0)))cells[i]=null;});
  if(s.variation==='turn')add(p.turn);
  for(const [id,edits] of Object.entries(s.edits))for(const [index,cell] of Object.entries(edits))pattern[id][Number(index)]=cell?{...cell}:null;
  return pattern;
}
export function stepDuration(s,index){return 60/s.bpm/meterOf(s).stepsPerBeat*(index%2===0?1+s.swing:1-s.swing);}
export function barDuration(s){return 60/s.bpm*meterOf(s).beats;}
const random=(seed)=>{let x=Math.imul(seed+17,1597334677);x^=x>>>15;return (x>>>0)/4294967296;};
export function eventsAt(s,pattern,index,cycle=0){
  const p=byId(s.groove),events=[];
  TRACKS.forEach(([id],track)=>{
    const cell=pattern[id][index];if(!cell||s.muted.includes(id)||s.volumes[id]===0||(id==='bass'&&!s.bassEnabled)||(['perc','shaker'].includes(id)&&!s.percussion))return;
    const seed=cycle*919+index*43+track*173;
    const offset=Math.max(-.013,Math.min(.03,(random(seed)-.5)*.024*s.human+(id==='snare'?p.late:0)));
    const velocity=Math.max(.05,Math.min(1,cell.v*(1+(random(seed+555)-.5)*.2*s.human)))*s.volumes[id];
    events.push({id,n:cell.n??0,velocity,offset});
    if(id==='hat'&&s.complexity>=55&&p.rolls?.includes(index)&&!(s.edits.hat&&Object.hasOwn(s.edits.hat,index))){const count=s.complexity>=85?3:2;for(let k=1;k<count;k++)events.push({id,n:0,velocity:velocity*(k%2?.65:.8),offset:offset+stepDuration(s,index)*k/count});}
  });return events;
}
export function validState(s){
  if(!s||s.version!==2||!byId(s.groove)||!Number.isFinite(s.bpm)||s.bpm<40||s.bpm>200||!Number.isInteger(s.root)||s.root<24||s.root>47)return false;
  if(!['main','open','turn'].includes(s.variation)||!Object.hasOwn(KITS,s.kit)||!['round','pluck','808'].includes(s.bassSound)||typeof s.bassEnabled!=='boolean'||typeof s.percussion!=='boolean')return false;
  if(![s.human,s.level].every(v=>Number.isFinite(v)&&v>=0&&v<=1)||!Number.isFinite(s.swing)||s.swing<0||s.swing>.4||!Number.isFinite(s.complexity)||s.complexity<0||s.complexity>100)return false;
  const ids=TRACKS.map(t=>t[0]);if(!Array.isArray(s.muted)||s.muted.some(id=>!ids.includes(id))||typeof s.words!=='string'||s.words.length>100000)return false;
  if(!s.volumes||!ids.every(id=>Number.isFinite(s.volumes[id])&&s.volumes[id]>=0&&s.volumes[id]<=1)||!s.edits||Array.isArray(s.edits)||typeof s.edits!=='object')return false;
  const n=meterOf(s).steps*2;
  return Object.entries(s.edits).every(([id,edits])=>ids.includes(id)&&edits&&typeof edits==='object'&&!Array.isArray(edits)&&Object.entries(edits).every(([i,c])=>/^\d+$/.test(i)&&Number(i)<n&&(c===null||(typeof c==='object'&&Number.isFinite(c.v)&&c.v>0&&c.v<=1&&(id!=='bass'||[0,2,3,5,7,10,12].includes(c.n))))));
}
export function migrate(s){
  if(validState(s))return clone(s);
  if(!s||s.version!==1||!s.pattern||!Number.isFinite(s.bpm)||s.bpm<40||s.bpm>200||!Array.isArray(s.muted)||typeof s.words!=='string')throw new Error('This is not a supported MaloSound sketch.');
  for(const id of ['kick','snare','hat','perc','bass'])if(!Array.isArray(s.pattern[id])||s.pattern[id].length!==16||!s.pattern[id].every(v=>id==='bass'?[null,0,3,5,7,10,12].includes(v):typeof v==='boolean'))throw new Error('The old sketch contains an invalid pattern.');
  const next=makeState('boom-bap');Object.assign(next,{bpm:s.bpm,swing:s.swing,root:s.root,level:s.level,words:s.words,bassEnabled:true,percussion:true,muted:s.muted,kit:'electronic',human:0});next.volumes.bass=s.bassLevel;
  for(const [id] of TRACKS){next.edits[id]={};for(let i=0;i<32;i++){const value=s.pattern[id]?.[i%16];next.edits[id][i]=id==='bass'?(value==null?null:{n:value,v:.75}):(value?{v:.85}:null);}}
  if(!validState(next))throw new Error('The old sketch contains invalid settings.');return next;
}
