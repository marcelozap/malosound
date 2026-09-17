import {byId,meterOf,stepDuration,eventsAt,patternFor,barDuration} from './grooves.mjs';

export function createEngine(ctx,level=.72){
  const bus=ctx.createGain(),compress=ctx.createDynamicsCompressor(),output=ctx.createGain();
  compress.threshold.value=-10;compress.knee.value=18;compress.ratio.value=3.5;compress.attack.value=.003;compress.release.value=.14;
  bus.connect(compress);compress.connect(output);output.connect(ctx.destination);output.gain.value=level;
  const noise=ctx.createBuffer(1,ctx.sampleRate,ctx.sampleRate),samples=noise.getChannelData(0);let seed=9377;
  for(let i=0;i<samples.length;i++){seed=(Math.imul(seed,1664525)+1013904223)|0;samples[i]=(seed>>>0)/2147483648-1;}
  return {ctx,bus,output,noise,openVoices:[],bassVoices:[]};
}
const profiles={
  acoustic:{kick:[126,49,.25],click:.065,snare:[183,.18,2200,.15],hat:[7900,.07],open:.3},
  vintage:{kick:[103,51,.17],click:.03,snare:[155,.11,1450,.095],hat:[5900,.046],open:.19},
  electronic:{kick:[170,43,.31],click:.12,snare:[230,.1,3300,.17],hat:[8800,.04],open:.24},
  '808':{kick:[98,40,.52],click:.022,snare:[175,.12,2000,.2],hat:[9800,.045],open:.38}
};
export function hit(engine,event,time,state,held){
  const {ctx:c,bus,noise}=engine,{id,velocity:v,n}=event,p=profiles[state.kit],groove=byId(state.groove),created=[];
  const keep=(node,length)=>{node.start(time);node.stop(time+length);created.push(node);if(held){held.add(node);node.onended=()=>held.delete(node);}return node;};
  const tone=(freq,end,duration,gain,type='sine',lowpass=0,attack=.004)=>{
    const osc=c.createOscillator(),env=c.createGain();osc.type=type;osc.frequency.setValueAtTime(freq,time);if(end!==freq)osc.frequency.exponentialRampToValueAtTime(end,time+duration*.7);
    env.gain.setValueAtTime(.0001,time);env.gain.exponentialRampToValueAtTime(Math.max(.0001,gain*v),time+attack);env.gain.exponentialRampToValueAtTime(.0001,time+duration);osc.connect(env);
    if(lowpass){const filter=c.createBiquadFilter();filter.type='lowpass';filter.frequency.value=lowpass;env.connect(filter);filter.connect(bus);}else env.connect(bus);
    return keep(osc,duration+.01);
  };
  const burst=(freq,duration,gain,type='highpass',delay=0)=>{
    const src=c.createBufferSource(),filter=c.createBiquadFilter(),env=c.createGain();src.buffer=noise;filter.type=type;filter.frequency.value=freq;filter.Q.value=.75;
    env.gain.setValueAtTime(0,time);env.gain.setValueAtTime(Math.max(.0001,gain*v),time+delay);env.gain.exponentialRampToValueAtTime(.0001,time+delay+duration);src.connect(filter);filter.connect(env);env.connect(bus);return keep(src,delay+duration+.01);
  };
  const choke=list=>{for(const node of list){try{node.stop(time);}catch{}}list.length=0;};
  if(id==='kick'){
    tone(p.kick[0],p.kick[1],p.kick[2],.88);burst(2400,.018,p.click,'lowpass');
    if(state.kit==='acoustic')tone(91,77,.14,.16,'triangle',1100);
  }else if(id==='snare'){
    if(groove.crossstick){tone(460,395,.06,.24,'triangle');tone(930,760,.025,.12,'square',3500);}
    else if(groove.brush){burst(2300,.24,.29,'bandpass');burst(6400,.15,.12);}
    else{tone(p.snare[0],p.snare[0]*.77,p.snare[1],.22,'triangle');burst(p.snare[2],p.snare[3],.38);if(state.kit==='acoustic')tone(335,310,.09,.09);if(state.kit==='electronic'||state.kit==='808'){burst(1800,.05,.17,'bandpass',.011);burst(2300,.08,.12,'bandpass',.023);}}
  }else if(id==='hat'||id==='open'){
    choke(engine.openVoices);const duration=id==='open'?p.open:p.hat[1];burst(p.hat[0],duration,.2);
    if(state.kit==='808'||state.kit==='electronic'){for(const f of [4100,5570,7330])tone(f,f,duration*.65,.026,'square',12000);}
    if(id==='open')engine.openVoices.push(...created);
  }else if(id==='perc'){
    if(groove.perc==='conga'){const low=event.index%8<4;const f=low?165:245;tone(f*1.15,f,.16,.48);tone(f*1.62,f*1.52,.08,.12);burst(1200,.023,.09,'bandpass');}
    else if(groove.perc==='bongo'){const f=event.index%8>=6?210:340;tone(f*1.1,f,.105,.44);tone(f*1.63,f*1.5,.06,.1);burst(2000,.025,.08,'bandpass');}
    else{tone(760,670,.043,.19,'triangle');tone(1290,1120,.027,.085,'square',3500);}
  }else if(id==='shaker'){
    if(groove.texture==='guira'||groove.texture==='guiro'){const freq=groove.texture==='guira'?6800:2350;const pulses=event.index%4===0?4:2;for(let i=0;i<pulses;i++)burst(freq,.022,.13,groove.texture==='guira'?'highpass':'bandpass',i*.02);}
    else{burst(5800,.062,.2);burst(7400,.04,.08,'highpass',.018);}
  }else if(id==='bass'){
    choke(engine.bassVoices);const f=440*2**((state.root+n-69)/12),beat=60/state.bpm;
    if(state.bassSound==='808'){tone(f*1.16,f,Math.min(1.8,beat*1.9),.49,'sine');tone(f,f,Math.min(.7,beat),.075,'triangle',330);}
    else if(state.bassSound==='pluck'){tone(f,f,beat*.38,.32,'triangle',1000,.002);tone(f*2,f*2,.065,.06);}
    else{tone(f,f,beat*.6,.34,'triangle',700);tone(f,f,beat*.6,.19);}
    engine.bassVoices.push(...created);
  }
}
export function scheduleStep(engine,state,pattern,index,time,cycle,held){
  const events=eventsAt(state,pattern,index,cycle);
  for(const event of events)hit(engine,{...event,index},Math.max(0,time+event.offset),state,held);
  return events.length;
}
export async function renderBeat(state,bars,OfflineContext=globalThis.OfflineAudioContext){
  if(!OfflineContext)throw new Error('Offline audio export is unavailable in this browser.');
  const tail=state.bassEnabled&&state.bassSound==='808'?2:.5;
  const duration=bars*barDuration(state),context=new OfflineContext(2,Math.ceil((duration+tail)*44100),44100),engine=createEngine(context,state.level),pattern=patternFor(state),m=meterOf(state);
  let time=0;for(let i=0;i<bars*m.steps;i++){scheduleStep(engine,state,pattern,i%(m.steps*2),time,Math.floor(i/(m.steps*2)));time+=stepDuration(state,i);}
  return {buffer:await context.startRendering(),duration,tail};
}
export function encodeWav(buffer){
  const frames=buffer.length,channels=buffer.numberOfChannels,bytes=frames*channels*2,array=new ArrayBuffer(44+bytes),view=new DataView(array),write=(offset,text)=>{for(let i=0;i<text.length;i++)view.setUint8(offset+i,text.charCodeAt(i));};
  write(0,'RIFF');view.setUint32(4,36+bytes,true);write(8,'WAVE');write(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,channels,true);view.setUint32(24,buffer.sampleRate,true);view.setUint32(28,buffer.sampleRate*channels*2,true);view.setUint16(32,channels*2,true);view.setUint16(34,16,true);write(36,'data');view.setUint32(40,bytes,true);
  const data=Array.from({length:channels},(_,i)=>buffer.getChannelData(i));let peak=0;for(const channel of data)for(let i=0;i<frames;i++)peak=Math.max(peak,Math.abs(channel[i]));const scale=peak>.98?.98/peak:1;
  for(let i=0;i<frames;i++)for(let channel=0;channel<channels;channel++){const sample=Math.max(-1,Math.min(1,data[channel][i]*scale));view.setInt16(44+(i*channels+channel)*2,sample*(sample<0?32768:32767),true);}
  return new Blob([array],{type:'audio/wav'});
}
