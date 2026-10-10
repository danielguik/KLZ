"use strict";
/* Motor de preview/edição: desenha as camadas num canvas (mesma aparência do render), toca áudio, timeline arrastável. */
const $=(s,e=document)=>e.querySelector(s);
const W=1080,H=1920;
const TYPES={video:'Vídeo',audio:'Áudio',captions:'Legendas',glass:'Vidro',title:'Título',stat:'Número',floatingWords:'Palavras flutuantes',flash:'Flash'};
const clone=o=>JSON.parse(JSON.stringify(o));
const rid=()=>'l'+Math.random().toString(36).slice(2,7);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt=t=>{t=Math.max(0,t);const m=Math.floor(t/60),s=t-m*60;return m+':'+(s<10?'0':'')+s.toFixed(2)};
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
function toast(m,ms=3500){const e=$('#toast');e.textContent=m;e.hidden=false;clearTimeout(toast.t);toast.t=setTimeout(()=>e.hidden=true,ms)}

const API={token:localStorage.getItem('klz-token')||'',pid:null};
function mediaUrl(rel){const [p,q]=String(rel).split('?');return `/api/projects/${API.pid}/files/${p}?${q?q+'&':''}token=${encodeURIComponent(API.token)}`}
async function api(path,opt={}){
  const o={...opt,headers:{'X-KLZ-Token':API.token,...(opt.headers||{})}};
  if(opt.json!==undefined){o.method=o.method||'POST';o.body=JSON.stringify(opt.json);o.headers['Content-Type']='application/json';delete o.json}
  const r=await fetch(path,o);
  if(r.status===401){const e=new Error('Senha inválida');e.code=401;throw e}
  if(!r.ok){let d='';try{d=(await r.json()).detail}catch(e){}throw new Error(d||('Erro '+r.status))}
  return r.json();
}

let PROJ=null;
const S={t:0,playing:false,sel:null,pps:12,hook:{}};
const cv=$('#cv'),ctx=cv.getContext('2d');
const tmp=document.createElement('canvas'),tctx=tmp.getContext('2d');
let K=cv.width/W;
const dur=()=>PROJ?PROJ.durationSec:1;
const LAY=()=>PROJ?PROJ.layers:[];
const layerEnd=l=>l.start+l.duration;

/* ---------- salvar camadas no servidor ---------- */
let saveTimer=null;
function saveLayersSoon(){
  clearTimeout(saveTimer);
  saveTimer=setTimeout(async()=>{
    if(!PROJ)return;
    try{await api(`/api/projects/${PROJ.id}/layers`,{method:'PUT',json:{layers:PROJ.layers,durationSec:PROJ.durationSec,mix:PROJ.mix,cover_old_subs:PROJ.cover_old_subs,pronounce:PROJ.pronounce}})}catch(e){toast('Não salvou: '+e.message)}
  },500);
}
function recalcDur(){const e=Math.max(...LAY().map(layerEnd),1);if(e>PROJ.durationSec)PROJ.durationSec=Math.round(e*100)/100}

/* ---------- mídia ---------- */
const media={vids:{},bufs:{},loading:{}};
let actx=null,bus=null;
function ensureAudio(){if(actx)return actx;actx=new (window.AudioContext||window.webkitAudioContext)();bus=actx.createGain();bus.connect(actx.destination);return actx}
async function loadBuf(u){
  if(media.bufs[u]||media.loading[u])return;media.loading[u]=1;
  try{const r=await fetch(u);const ab=await r.arrayBuffer();media.bufs[u]=await ensureAudio().decodeAudioData(ab)}catch(e){}finally{delete media.loading[u]}
}
function prepareMedia(){
  for(const l of LAY()){
    if(l.type==='audio')loadBuf(mediaUrl(l.src));
    if(l.type==='video'){
      const u=mediaUrl(l.src);let v=media.vids[l.id];
      if(!v||v._u!==u){
        if(v){try{v.pause();v.remove()}catch(e){}}
        v=document.createElement('video');v._u=u;v.src=u;v.playsInline=true;v.preload='auto';v.crossOrigin='anonymous';
        v.style.cssText='position:fixed;left:-9999px;top:0;width:2px;height:2px;opacity:0;pointer-events:none';document.body.appendChild(v);media.vids[l.id]=v;
      }
    }
  }
}
function wireVideoAudio(v){if(v._src)return;ensureAudio();v._src=actx.createMediaElementSource(v);v._gain=actx.createGain();v._src.connect(v._gain);v._gain.connect(bus)}

/* ---------- animação ---------- */
function sp(t,d=14,s=140,m=1){if(t<=0)return 0;const w0=Math.sqrt(s/m),z=d/(2*Math.sqrt(s*m));
  if(z<1){const wd=w0*Math.sqrt(1-z*z);return 1-Math.exp(-z*w0*t)*(Math.cos(wd*t)+(z*w0/wd)*Math.sin(wd*t))}return 1-Math.exp(-w0*t)*(1+w0*t)}
const lerp=(x,a,b,c,d)=>x<=a?c:x>=b?d:c+(d-c)*(x-a)/(b-a);
const FONT=(w,px)=>`${w} ${px}px Manrope, 'DM Sans', system-ui, sans-serif`;
function rrect(x,y,w,h,r){r=Math.min(r,w/2,h/2);ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath()}
function enterOut(l,lt){return{inn:sp(lt),out:lerp(lt,l.duration-.27,l.duration,1,0)}}
function coverRect(v){const sc=Math.max(W/v.videoWidth,H/v.videoHeight),w=v.videoWidth*sc,h=v.videoHeight*sc;return{x:(W-w)/2,y:(H-h)/2,w,h,sc}}

/* ---------- desenho ---------- */
function drawVideo(l,lt){
  const v=media.vids[l.id];if(!v||v.readyState<2||!v.videoWidth)return;
  let z=1;for(const p of(l.zoomPunches||[])){const a=p.at,s0=p.scale;let q=1;
    if(lt>=a&&lt<a+.25)q=1+(s0-1)*(lt-a)/.25;else if(lt>=a+.25&&lt<a+p.hold)q=s0;else if(lt>=a+p.hold&&lt<a+p.hold+.3)q=s0-(s0-1)*(lt-a-p.hold)/.3;z=Math.max(z,q)}
  const sc=Math.max(W/v.videoWidth,H/v.videoHeight)*z,w=v.videoWidth*sc,h=v.videoHeight*sc;
  ctx.save();ctx.filter=`brightness(${l.brightness??1}) contrast(${l.contrast??1}) saturate(${l.saturate??1})`;ctx.drawImage(v,(W-w)/2,(H-h)/2,w,h);ctx.restore();
}
function drawGlass(l,lt){
  const{inn,out}=l.enter?enterOut(l,lt):{inn:1,out:1};const x=l.x*W,y=l.y*H,w=l.w*W,h=l.h*H,sc=.94+.06*inn;
  tmp.width=cv.width;tmp.height=cv.height;tctx.drawImage(cv,0,0);
  ctx.save();ctx.globalAlpha=clamp(out*inn,0,1);ctx.translate(x+w/2,y+h/2);ctx.scale(sc,sc);ctx.translate(-(x+w/2),-(y+h/2));
  rrect(x,y,w,h,l.radius);ctx.save();ctx.clip();ctx.setTransform(1,0,0,1,0,0);ctx.filter=`blur(${l.blur*K}px)`;ctx.drawImage(tmp,0,0);ctx.filter='none';ctx.restore();
  rrect(x,y,w,h,l.radius);ctx.fillStyle=l.tint;ctx.fill();ctx.lineWidth=2;ctx.strokeStyle=l.borderColor;rrect(x+1,y+1,w-2,h-2,l.radius);ctx.stroke();ctx.restore();
}
function drawTitle(l,lt){
  const{inn,out}=enterOut(l,lt);const y=l.y*H;ctx.save();ctx.globalAlpha=clamp(out*inn,0,1);ctx.translate(W/2,y+(1-inn)*40);ctx.scale(.9+.1*inn,.9+.1*inn);
  ctx.textAlign='center';ctx.textBaseline='top';let ty=0;
  if(l.tag){const fs=l.fontSize*.3;ctx.font=FONT(800,fs);const t=l.tag.toUpperCase(),tw=ctx.measureText(t).width+t.length*4;
    ctx.fillStyle='rgba(255,255,255,.12)';rrect(-tw/2-26,0,tw+52,fs+22,14);ctx.fill();ctx.lineWidth=1.5;ctx.strokeStyle='rgba(255,255,255,.35)';ctx.stroke();
    ctx.fillStyle=l.accent;ctx.textBaseline='middle';if('letterSpacing'in ctx)ctx.letterSpacing='4px';ctx.fillText(t,0,(fs+22)/2);if('letterSpacing'in ctx)ctx.letterSpacing='0px';ctx.textBaseline='top';ty=fs+22+18}
  ctx.font=FONT(800,l.fontSize);ctx.shadowColor='rgba(0,0,0,.5)';ctx.shadowBlur=30*K;ctx.shadowOffsetY=6*K;
  const words=l.text.split(' '),ws=words.map(w=>ctx.measureText(w+' ').width);let tot=ws.reduce((a,b)=>a+b,0)-ctx.measureText(' ').width,x=-tot/2;
  ctx.textAlign='left';words.forEach((w,i)=>{ctx.fillStyle=(l.accentLast&&i===words.length-1)?l.accent:l.color;ctx.fillText(w,x,ty);x+=ws[i]});ctx.restore();
}
function drawStat(l,lt){
  const{inn,out}=enterOut(l,lt);const w=W*.62,h=330,x=(W-w)/2,y=l.y*H;
  ctx.save();ctx.globalAlpha=clamp(out*inn,0,1);ctx.translate(W/2,y+h/2);ctx.scale(.9+.1*inn,.9+.1*inn);ctx.translate(-W/2,-(y+h/2));
  ctx.fillStyle='rgba(12,12,18,.62)';rrect(x,y,w,h,34);ctx.fill();ctx.lineWidth=2;ctx.strokeStyle='rgba(255,255,255,.3)';ctx.stroke();
  ctx.textBaseline='top';ctx.textAlign='left';ctx.fillStyle=l.color;ctx.font=FONT(800,32);if('letterSpacing'in ctx)ctx.letterSpacing='3px';ctx.fillText(l.label.toUpperCase(),x+40,y+30);if('letterSpacing'in ctx)ctx.letterSpacing='0px';
  const c=lerp(lt,.2,1.4,0,l.value);ctx.fillStyle=l.accent;ctx.font=FONT(800,150);const ns=String(Math.round(c));ctx.fillText(ns,x+40,y+72);const nw=ctx.measureText(ns).width;ctx.font=FONT(800,60);ctx.fillText(l.suffix,x+40+nw+10,y+150);
  const bar=clamp(c/Math.max(Math.abs(l.value),1),0,1);ctx.fillStyle='rgba(255,255,255,.18)';rrect(x+40,y+h-52,w-80,16,8);ctx.fill();if(bar>0){ctx.fillStyle=l.accent;rrect(x+40,y+h-52,(w-80)*bar,16,8);ctx.fill()}ctx.restore();
}
function drawFloating(l,lt){
  const{out}=enterOut(l,lt);
  l.words.forEach((w,i)=>{const a=(i*137.5)%360,x=W*(.18+.64*((Math.sin(i*2.3)+1)/2)),y=H*(.06+.2*((Math.cos(i*1.7)+1)/2))+Math.sin((lt*30+i*20)/30)*8,ap=sp(lt-i*.13);
    ctx.save();ctx.globalAlpha=clamp(out*.85*ap,0,1);ctx.translate(x,y);ctx.rotate((((a%24)-12)*Math.PI)/180);ctx.scale(ap,ap);ctx.font=FONT(800,l.fontSize*(.8+((i*7)%5)/10));ctx.fillStyle=l.color;ctx.textAlign='center';ctx.textBaseline='middle';ctx.shadowColor='rgba(0,0,0,.5)';ctx.shadowBlur=20*K;ctx.fillText(w,0,0);ctx.restore()});
}
function drawFlash(l,lt){const o=lt<.1?lerp(lt,0,.1,0,.9):lerp(lt,.1,l.duration,.9,0);ctx.save();ctx.globalAlpha=o;ctx.fillStyle=l.color;ctx.fillRect(0,0,W,H);ctx.restore()}
let capCache={};
function groupsOf(l){const c=capCache[l.id];if(c&&c.ref===l.words&&c.mc===l.maxChars&&c.mw===l.maxWords)return c.g;
  const out=[];let cur=[];for(const w of l.words){const ch=cur.reduce((a,x)=>a+x.text.length+1,0)+w.text.length;if(cur.length&&(cur.length>=l.maxWords||ch>l.maxChars||w.p!==cur[cur.length-1].p)){out.push(cur);cur=[]}cur.push(w)}
  if(cur.length)out.push(cur);capCache[l.id]={ref:l.words,mc:l.maxChars,mw:l.maxWords,g:out};return out}
function drawCaptions(l,lt){
  const g=groupsOf(l).find(gr=>lt>=gr[0].start-.02&&lt<=gr[gr.length-1].end+.12);if(!g)return;
  ctx.save();ctx.font=FONT(800,l.fontSize);ctx.textBaseline='middle';ctx.textAlign='left';
  const gap=l.fontSize*.32,ws=g.map(w=>ctx.measureText(w.text).width);let tot=ws.reduce((a,b)=>a+b,0)+gap*(g.length-1),x=(W-tot)/2;const y=l.y*H;
  ctx.shadowColor='rgba(0,0,0,.6)';ctx.shadowBlur=18*K;ctx.shadowOffsetY=4*K;
  g.forEach((w,i)=>{const spoken=lt>=w.start,pop=spoken?sp(lt-w.start,12,220,.6):0,cur=spoken&&lt<w.end,s=spoken?(.82+.18*pop+(cur?.06:0)):1;
    ctx.save();ctx.globalAlpha=spoken?1:.32;ctx.translate(x+ws[i]/2,y);ctx.scale(s,s);ctx.fillStyle=(w.key&&spoken)?l.highlight:l.color;ctx.textAlign='center';ctx.fillText(w.text,0,0);ctx.restore();x+=ws[i]+gap});
  ctx.restore();
}
function draw(){
  K=cv.width/W;ctx.setTransform(K,0,0,K,0,0);ctx.fillStyle='#000';ctx.fillRect(0,0,W,H);
  for(const l of LAY()){const lt=S.t-l.start;if(lt<0||lt>=l.duration)continue;ctx.save();ctx.setTransform(K,0,0,K,0,0);
    try{({video:drawVideo,glass:drawGlass,title:drawTitle,stat:drawStat,floatingWords:drawFloating,captions:drawCaptions,flash:drawFlash}[l.type]||(()=>{}))(l,lt)}catch(e){}ctx.restore()}
}

/* ---------- reprodução ---------- */
let srcs=[],t0=0,tS=0;
function stopMedia(){for(const s of srcs){try{s.stop()}catch(e){}}srcs=[];for(const v of Object.values(media.vids))try{v.pause()}catch(e){}}
function scheduleAudio(from){
  if(!actx)return;
  for(const l of LAY()){if(l.type!=='audio')continue;const b=media.bufs[mediaUrl(l.src)];if(!b)continue;const end=layerEnd(l);if(end<=from)continue;
    const s=actx.createBufferSource(),g=actx.createGain();s.buffer=b;s.playbackRate.value=l.rate||1;g.gain.value=l.volume??1;s.connect(g);g.connect(bus);
    const when=actx.currentTime+Math.max(0,l.start-from),off=(l.trimStart||0)+Math.max(0,from-l.start)*(l.rate||1),left=(end-Math.max(from,l.start))*(l.rate||1);
    try{s.start(when,off,left)}catch(e){}srcs.push(s)}
}
function syncVideos(){
  for(const l of LAY()){if(l.type!=='video')continue;const v=media.vids[l.id];if(!v)continue;wireVideoAudio(v);v._gain.gain.value=l.volume??1;
    const lt=S.t-l.start,active=lt>=0&&lt<l.duration,target=(l.trimStart||0)+lt;
    if(S.playing&&active){if(v.paused||Math.abs(v.currentTime-target)>.3){try{v.currentTime=target}catch(e){}v.play().catch(()=>{})}}
    else{if(!v.paused)v.pause();if(active&&Math.abs(v.currentTime-target)>.04){try{v.currentTime=target}catch(e){}}}}
}
function play(){if(S.playing||!PROJ)return;ensureAudio();actx.resume();if(S.t>=dur()-.05)S.t=0;S.playing=true;t0=performance.now();tS=S.t;scheduleAudio(S.t);syncVideos();$('#bPlay').textContent='❚❚ Pausar'}
function pause(){if(!S.playing)return;S.playing=false;stopMedia();$('#bPlay').textContent='▶ Tocar'}
function seek(t){const was=S.playing;if(was)pause();S.t=clamp(t,0,dur());syncVideos();if(was)play();updatePH()}
function loop(){
  if(S.playing){S.t=tS+(performance.now()-t0)/1000;if(S.t>=dur()){S.t=dur();pause()}else syncVideos()}else if(PROJ)syncVideos();
  if(PROJ)draw();updatePH();if(S.hook.frame)S.hook.frame();requestAnimationFrame(loop);
}
function updatePH(){$('#tc').textContent=fmt(S.t)+' / '+fmt(dur());$('#ph').style.left=(S.t*S.pps)+'px'}
function playRange(a,b){seek(a);play();clearTimeout(playRange.t);playRange.t=setTimeout(()=>pause(),(b-a)*1000+150)}

/* ---------- lista de camadas e timeline ---------- */
function renderLayers(){
  $('#llist').innerHTML=[...LAY()].reverse().map(l=>`<div class="lrow ${l.id===S.sel?'sel':''}" data-id="${l.id}"><span class="dot" style="background:var(--c-${l.type})"></span><span class="nm">${esc(l.name)}</span><small>${TYPES[l.type]}</small></div>`).join('')||'<div class="hint">Sem camadas ainda. Crie um projeto e analise um vídeo.</div>';
  document.querySelectorAll('.lrow').forEach(e=>e.onclick=()=>select(e.dataset.id));
}
function renderTimeline(){
  const end=Math.max(dur()+2,10),width=end*S.pps;$('#tlin').style.width=(150+width)+'px';$('#ruler').style.width=width+'px';
  const step=S.pps>=30?1:S.pps>=14?2:5;$('#ruler').innerHTML=Array.from({length:Math.ceil(end/step)},(_,i)=>`<span style="left:${i*step*S.pps}px">${i*step}s</span>`).join('');
  $('#rows').innerHTML=[...LAY()].reverse().map(l=>`<div class="trow ${l.id===S.sel?'sel':''}" data-id="${l.id}"><div class="tname">${esc(l.name)}</div><div class="lane" style="min-width:${width}px"><div class="clip ${l.id===S.sel?'sel':''}" data-id="${l.id}" style="left:${l.start*S.pps}px;width:${Math.max(6,l.duration*S.pps)}px;background:var(--c-${l.type})">${esc(l.name)}<span class="rz"></span></div></div></div>`).join('');
  document.querySelectorAll('.clip').forEach(c=>{c.onpointerdown=e=>{e.preventDefault();const id=c.dataset.id,l=LAY().find(x=>x.id===id);selectSoft(id);
    const x0=e.clientX,s0=l.start,d0=l.duration,resize=e.target.classList.contains('rz');c.setPointerCapture(e.pointerId);
    const mv=ev=>{const dx=(ev.clientX-x0)/S.pps;if(resize){l.duration=Math.max(.1,Math.round((d0+dx)*20)/20);c.style.width=Math.max(6,l.duration*S.pps)+'px'}else{l.start=Math.max(0,Math.round((s0+dx)*20)/20);c.style.left=l.start*S.pps+'px'}};
    const up=()=>{c.removeEventListener('pointermove',mv);c.removeEventListener('pointerup',up);recalcDur();saveLayersSoon();renderAll()};c.addEventListener('pointermove',mv);c.addEventListener('pointerup',up)}});
  document.querySelectorAll('.trow .tname').forEach(n=>n.onclick=()=>select(n.parentElement.dataset.id));
}
$('#ruler').onpointerdown=e=>{const r=$('#ruler').getBoundingClientRect();const mv=ev=>seek((ev.clientX-r.left)/S.pps);mv(e);const up=()=>{removeEventListener('pointermove',mv);removeEventListener('pointerup',up)};addEventListener('pointermove',mv);addEventListener('pointerup',up)};
$('#zoom').oninput=e=>{S.pps=+e.target.value;renderTimeline();updatePH()};
function selectSoft(id){S.sel=id;renderLayers();if(S.hook.inspector)S.hook.inspector();document.querySelectorAll('.clip').forEach(c=>c.classList.toggle('sel',c.dataset.id===id));document.querySelectorAll('.trow').forEach(r=>r.classList.toggle('sel',r.dataset.id===id))}
function select(id){S.sel=id;renderAll()}
function renderAll(){renderLayers();renderTimeline();if(S.hook.inspector)S.hook.inspector();updatePH()}

/* cortar no playhead */
$('#bCut').onclick=()=>{const l=LAY().find(x=>x.id===S.sel);if(!l)return toast('Selecione uma camada para cortar.');const rel=S.t-l.start;if(rel<=.05||rel>=l.duration-.05)return toast('Coloque o playhead dentro da camada.');
  const r=clone(l);r.id=rid();r.auto=false;delete r.phrase;r.name=l.name+' (2)';r.start=+S.t.toFixed(2);r.duration=+(l.duration-rel).toFixed(3);
  if(l.type==='video'||l.type==='audio')r.trimStart=+((l.trimStart||0)+rel*(l.rate||1)).toFixed(3);l.duration=+rel.toFixed(3);PROJ.layers.splice(PROJ.layers.indexOf(l)+1,0,r);S.sel=r.id;saveLayersSoon();renderAll()};
$('#bStart').onclick=()=>seek(0);$('#bPlay').onclick=()=>S.playing?pause():play();
addEventListener('keydown',e=>{if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();S.playing?pause():play()}});

function setProject(p){PROJ=p;capCache={};prepareMedia();if(S.sel&&!LAY().find(l=>l.id===S.sel))S.sel=null;renderAll()}
requestAnimationFrame(loop);
