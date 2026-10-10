"use strict";
/* Motor de preview/edição: desenha as camadas num canvas (mesma aparência do render), toca áudio, timeline arrastável. */
const $=(s,e=document)=>e.querySelector(s);
const W=1080,H=1920;
const TYPES={video:'Vídeo',audio:'Áudio',captions:'Legendas',glass:'Vidro',title:'Título',stat:'Número',floatingWords:'Palavras flutuantes',flash:'Flash',background:'Fundo animado',videoCard:'Vídeo em cartão',kinetic:'Texto cinético',barchart:'Gráfico de barras',ring:'Anel',lowerthird:'Identificação',callout:'Seta/legenda',grid3d:'Grade 3D',shape:'Forma',transition:'Transição'};
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
const dur=()=>PROJ?PROJ.durationSec:1;
const LAY=()=>PROJ?PROJ.layers:[];
const layerEnd=l=>l.start+l.duration;

/* ---------- salvar camadas no servidor ---------- */
let saveTimer=null;
function saveLayersSoon(){
  refreshPlayer();
  clearTimeout(saveTimer);
  saveTimer=setTimeout(async()=>{
    if(!PROJ)return;
    try{await api(`/api/projects/${PROJ.id}/layers`,{method:'PUT',json:{layers:PROJ.layers,durationSec:PROJ.durationSec,mix:PROJ.mix,cover_old_subs:PROJ.cover_old_subs,pronounce:PROJ.pronounce}})}catch(e){toast('Não salvou: '+e.message)}
  },500);
}
function recalcDur(){const e=Math.max(...LAY().map(layerEnd),1);if(e>PROJ.durationSec)PROJ.durationSec=Math.round(e*100)/100}

/* ---------- prévia = player do Remotion (mesmo código do render final) ---------- */
let PLAYER=null,capCache={};
function ensurePlayer(){if(!PLAYER&&window.KLZPlayer)PLAYER=KLZPlayer.mount($('#pl'));return PLAYER}
function playerProps(){return{fps:PROJ.fps||30,width:PROJ.width||1080,height:PROJ.height||1920,durationSec:PROJ.durationSec,layers:PROJ.layers.map(l=>l.src?{...l,src:location.origin+mediaUrl(l.src)}:l)}}
let rafPending=false;
function refreshPlayer(){
  if(rafPending||!PROJ)return;rafPending=true;
  requestAnimationFrame(()=>{rafPending=false;try{const p=ensurePlayer();if(p)p.update(playerProps())}catch(e){toast('Erro na prévia: '+String(e.message).slice(0,160),6000)}});
}
const prepareMedia=()=>refreshPlayer();
function play(){const p=ensurePlayer();if(!p||!PROJ)return;if(S.t>=dur()-.05)p.seekTo(0);p.play()}
function pause(){const p=ensurePlayer();if(p)p.pause()}
function seek(t){S.t=clamp(t,0,dur());const p=ensurePlayer();if(p)p.seekTo(Math.round(S.t*(PROJ.fps||30)));updatePH()}
function loop(){
  const p=PLAYER;
  if(p&&PROJ){const f=p.frame();S.t=f/(PROJ.fps||30);const pl=p.playing();if(pl!==S.playing){S.playing=pl;$('#bPlay').textContent=pl?'❚❚ Pausar':'▶ Tocar'}}
  updatePH();if(S.hook.frame)S.hook.frame();requestAnimationFrame(loop);
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

function setProject(p){PROJ=p;capCache={};refreshPlayer();if(S.sel&&!LAY().find(l=>l.id===S.sel))S.sel=null;renderAll()}
requestAnimationFrame(loop);
