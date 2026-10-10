"use strict";
/* Painéis da direita: Camada | Frases | Vozes | Lip-sync | Áudio | Saída */
let TAB='frases';let CAPS={};let JOBS=[];
const TABS=[['camada','Camada'],['frases','Frases'],['vozes','Vozes'],['lipsync','Lip-sync'],['audio','Áudio'],['saida','Saída']];
const stale=()=>(PROJ&&PROJ.stale)||[];
const spk=id=>(PROJ.speakers||[]).find(s=>s.id===id);
const voiceOf=sid=>{const s=spk(sid);return s&&(PROJ.voices||[]).find(v=>v.id===s.voice)};
const busy=kind=>JOBS.some(j=>(j.status==='rodando'||j.status==='na fila')&&(!kind||j.kind===kind));
S.hook.inspector=()=>renderTab();

function renderTabs(){
  $('#tabs').innerHTML=TABS.map(([k,l])=>`<button data-t="${k}" class="${k===TAB?'on':''}">${l}${k==='frases'&&stale().length?`<b>${stale().length}</b>`:''}</button>`).join('');
  document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{TAB=b.dataset.t;renderTab()});
}
function renderTab(){
  renderTabs();const b=$('#tabbody');
  if(!PROJ){b.innerHTML='<div class="hint">Crie um projeto (+ Novo) para começar.</div>';return}
  ({camada:tabCamada,frases:tabFrases,vozes:tabVozes,lipsync:tabLipsync,audio:tabAudio,saida:tabSaida})[TAB](b);
  if(S.hook.lsbox)S.hook.lsbox();
}
async function flushSave(){clearTimeout(saveTimer);if(!PROJ)return;await api(`/api/projects/${PROJ.id}/layers`,{method:'PUT',json:{layers:PROJ.layers,durationSec:PROJ.durationSec,mix:PROJ.mix,cover_old_subs:PROJ.cover_old_subs,pronounce:PROJ.pronounce}}).catch(()=>{})}
async function startJob(path,json,label){
  try{await flushSave();const j=await api(path,{method:'POST',json:json??{}});S.hook.trackJobs&&S.hook.trackJobs();return j}
  catch(e){toast(e.message);return null}
}
function jobDone(id){return new Promise(res=>{const t=setInterval(()=>{const j=JOBS.find(x=>x.id===id);if(j&&(j.status==='pronto'||j.status==='erro')){clearInterval(t);res(j)}},700)})}

/* ---------- Camada ---------- */
const FIELDS={
 common:[['name','text','Nome'],['start','num','Início (s)',0,900,.05],['duration','num','Duração (s)',.1,900,.05]],
 video:[['trimStart','num','Cortar início (s)',0,900,.05],['volume','range','Volume',0,1,.05],['brightness','range','Brilho',0,2,.05],['contrast','range','Contraste',0,2,.05],['saturate','range','Saturação',0,2,.05]],
 audio:[['volume','range','Volume',0,1.5,.05],['rate','range','Velocidade',.5,2,.01],['trimStart','num','Cortar início (s)',0,60,.05]],
 captions:[['fontSize','num','Tamanho',20,160,1],['y','range','Posição vertical',0,1,.01],['color','color','Cor'],['highlight','color','Cor de destaque'],['maxChars','num','Máx. caracteres por linha',6,40,1],['maxWords','num','Máx. palavras por linha',1,8,1]],
 glass:[['x','range','Posição X',0,1,.01],['y','range','Posição Y',0,1,.01],['w','range','Largura',0,1,.01],['h','range','Altura',0,1,.01],['radius','num','Arredondamento',0,200,1],['blur','range','Desfoque',0,80,1],['tint','color','Cor da película'],['borderColor','color','Cor da borda'],['enter','bool','Animação de entrada']],
 title:[['text','text','Texto'],['tag','text','Etiqueta (opcional)'],['y','range','Posição vertical',0,1,.01],['fontSize','num','Tamanho',20,260,1],['color','color','Cor'],['accent','color','Cor de destaque'],['accentLast','bool','Última palavra em destaque']],
 stat:[['label','text','Rótulo'],['value','num','Valor',-9999,9999,1],['suffix','text','Sufixo'],['y','range','Posição vertical',0,1,.01],['color','color','Cor'],['accent','color','Cor de destaque']],
 floatingWords:[['words','list','Palavras (uma por linha)'],['color','color','Cor'],['fontSize','num','Tamanho',20,160,1]],
 flash:[['color','color','Cor']]
};
const isHex=c=>/^#[0-9a-f]{6}$/i.test(c||'');
function field(l,f){const[k,type,label,mn,mx,st]=f,v=l[k];
  if(type==='bool')return`<label class="chk"><input type="checkbox" data-k="${k}" ${v?'checked':''}> ${label}</label>`;
  if(type==='range')return`<div class="fld"><label>${label}<output>${(+v).toFixed(2)}</output></label><input type="range" data-k="${k}" min="${mn}" max="${mx}" step="${st}" value="${v}"></div>`;
  if(type==='num')return`<div class="fld"><label>${label}</label><input type="number" data-k="${k}" min="${mn}" max="${mx}" step="${st}" value="${v}"></div>`;
  if(type==='color')return`<div class="fld"><label>${label}</label><div class="row2"><input type="text" data-k="${k}" value="${esc(v)}">${isHex(v)?`<input type="color" data-kc="${k}" value="${v}">`:''}</div></div>`;
  if(type==='list')return`<div class="fld"><label>${label}</label><textarea data-k="${k}" data-list="1" rows="5">${esc((v||[]).join('\n'))}</textarea></div>`;
  return`<div class="fld"><label>${label}</label><input type="text" data-k="${k}" value="${esc(v)}"></div>`}
function tabCamada(b){
  const l=LAY().find(x=>x.id===S.sel);
  if(!l){b.innerHTML='<div class="hint">Clique numa camada (lista ou timeline) para editar. As mudanças aparecem na hora no preview e são salvas sozinhas.</div>';return}
  let h=`<div class="btnrow"><button data-act="up">↑ Subir</button><button data-act="down">↓ Descer</button><button data-act="dup">Duplicar</button><button data-act="del" class="danger">Excluir</button></div>`;
  if(l.auto)h+='<div class="hint">Camada automática: as suas edições aqui são mantidas ao refazer vozes. Textos e vozes se editam na aba Frases.</div>';
  h+=FIELDS.common.map(f=>field(l,f)).join('')+(FIELDS[l.type]||[]).map(f=>field(l,f)).join('');
  if(l.type==='video'){h+=`<div class="ph"><span>Zoom em momentos-chave</span><button class="sm" data-act="addzp">+ Zoom</button></div>`;
    h+=(l.zoomPunches||[]).map((z,i)=>`<div class="zp"><div><small>em (s)</small><input type="number" step="0.05" data-zp="${i}" data-f="at" value="${z.at}"></div><div><small>escala</small><input type="number" step="0.01" min="1" max="2" data-zp="${i}" data-f="scale" value="${z.scale}"></div><div><small>duração</small><input type="number" step="0.05" data-zp="${i}" data-f="hold" value="${z.hold}"></div><button data-delzp="${i}" class="danger sm">✕</button></div>`).join('')||'<div class="hint">Nenhum zoom. Adicione para dar ênfase.</div>'}
  b.innerHTML=h;
  b.querySelectorAll('[data-k]').forEach(el=>{const k=el.dataset.k;el.addEventListener('input',()=>{let v;
    if(el.type==='checkbox')v=el.checked;else if(el.type==='range'||el.type==='number')v=+el.value;else if(el.dataset.list)v=el.value.split('\n').map(s=>s.trim()).filter(Boolean);else v=el.value;
    l[k]=v;if(k==='start'||k==='duration')recalcDur();saveLayersSoon();const o=el.parentElement.querySelector('output');if(o)o.textContent=(+v).toFixed(2);
    if(k==='name'||k==='start'||k==='duration'){renderLayers();renderTimeline()}const cc=b.querySelector(`[data-kc="${k}"]`);if(cc&&isHex(v))cc.value=v})});
  b.querySelectorAll('[data-kc]').forEach(el=>el.addEventListener('input',()=>{const k=el.dataset.kc;l[k]=el.value;const t=b.querySelector(`[data-k="${k}"]`);if(t)t.value=el.value;saveLayersSoon()}));
  b.querySelectorAll('[data-zp]').forEach(el=>el.addEventListener('input',()=>{l.zoomPunches[+el.dataset.zp][el.dataset.f]=+el.value;saveLayersSoon()}));
  b.querySelectorAll('[data-delzp]').forEach(el=>el.onclick=()=>{l.zoomPunches.splice(+el.dataset.delzp,1);saveLayersSoon();renderTab()});
  b.querySelectorAll('[data-act]').forEach(el=>el.onclick=()=>layerAct(el.dataset.act,l));
}
function layerAct(a,l){const L=LAY(),i=L.indexOf(l);
  if(a==='up'&&i<L.length-1)[L[i],L[i+1]]=[L[i+1],L[i]];else if(a==='down'&&i>0)[L[i],L[i-1]]=[L[i-1],L[i]];
  else if(a==='dup'){const c=clone(l);c.id=rid();c.auto=false;delete c.phrase;c.name+=' (cópia)';c.start=+(l.start+.5).toFixed(2);L.splice(i+1,0,c);S.sel=c.id}
  else if(a==='del'){L.splice(i,1);S.sel=null}else if(a==='addzp'){l.zoomPunches=l.zoomPunches||[];l.zoomPunches.push({at:+(S.t-l.start).toFixed(2),scale:1.15,hold:.8})}
  saveLayersSoon();renderAll()}
const NEW={title:()=>({type:'title',name:'Título',duration:3,text:'Novo título',tag:'',y:.12,fontSize:96,color:'#ffffff',accent:'#ffb020',accentLast:true}),
 stat:()=>({type:'stat',name:'Número',duration:3.6,label:'Rótulo',value:50,suffix:'%',y:.1,color:'#ffffff',accent:'#ffb020'}),
 glass:()=>({type:'glass',name:'Vidro',duration:4,enter:true,x:.1,y:.4,w:.8,h:.15,radius:36,blur:28,tint:'rgba(10,10,14,0.45)',borderColor:'rgba(255,255,255,0.45)'}),
 floatingWords:()=>({type:'floatingWords',name:'Palavras flutuantes',duration:4,words:['palavra','chave','destaque'],color:'#ffffff',fontSize:54}),
 flash:()=>({type:'flash',name:'Flash',duration:.4,color:'#ffffff'})};
function buildAdd(){const m=$('#addmenu');m.innerHTML=Object.keys(NEW).map(k=>`<button data-add="${k}">${TYPES[k]}</button>`).join('');
  m.querySelectorAll('[data-add]').forEach(b=>b.onclick=()=>{if(!PROJ)return toast('Abra um projeto primeiro.');const l={id:rid(),auto:false,start:+S.t.toFixed(2),...NEW[b.dataset.add]()};PROJ.layers.push(l);recalcDur();S.sel=l.id;saveLayersSoon();TAB='camada';renderAll()})}

/* ---------- Frases ---------- */
function statusOf(ph){
  if(ph.audio&&!stale().includes(ph.id)&&(ph.overflow||0)>0.35)return[`longa demais (+${ph.overflow.toFixed(1)}s)`,'stale'];
  if(!ph.en||!ph.en.trim())return['sem tradução','none'];
  if(stale().includes(ph.id))return[ph.audio?'desatualizada':'sem voz','stale'];
  return['voz ok','ok']}
function tabFrases(b){
  const ph=PROJ.phrases||[];
  if(!ph.length){b.innerHTML=`<div class="hint">Ainda não há frases.</div>`+analyzeForm();S.hook.analyze&&S.hook.analyze();return}
  const n=stale().length;
  let h=`<div class="btnrow">${CAPS.translate?`<button data-a="trans" ${busy('translate')?'disabled':''}>Traduzir tudo (Claude)</button>`:''}<button class="primary" data-a="voiceall" ${n&&!busy('voice')?'':'disabled'}>Gerar voz (${n} pendentes)</button></div>`;
  if(!CAPS.translate)h+='<div class="hint">Tradução automática desligada (falta a chave ANTHROPIC_API_KEY no servidor). Digite o inglês em cada frase.</div>';
  h+=ph.map(p=>{const[st,cl]=statusOf(p);const need=stale().includes(p.id)&&p.en&&p.en.trim();
    return`<div class="phr" data-id="${p.id}"><div class="meta"><span class="sw" style="background:${(spk(p.speaker)||{}).color||'#888'}"></span>
      <select data-spk="${p.id}">${(PROJ.speakers||[]).map(s=>`<option value="${s.id}" ${s.id===p.speaker?'selected':''}>${esc(s.name)}</option>`).join('')}</select>
      <button class="sm" data-play="${p.id}" title="Tocar este trecho">▶</button><span>${fmt(p.s)}–${fmt(p.e)}</span><span style="flex:1"></span><span class="badge ${cl}" id="bd_${p.id}">${st}</span></div>
      <details class="ptbox"><summary class="pt">${esc(p.pt)}</summary><textarea data-pt="${p.id}" rows="2">${esc(p.pt)}</textarea><div class="hint" style="padding:2px 0">Corrigir o português só ajuda a tradução automática; a voz usa o inglês abaixo.</div></details>
      <textarea data-en="${p.id}" rows="2" placeholder="Tradução em inglês… (use *asteriscos* para destacar)">${esc(p.en||'')}</textarea>
      <div class="row2" id="act_${p.id}"><button class="sm ghost" data-merge="${p.id}" title="Juntar com a frase seguinte">⤓ Juntar com a próxima</button>${need?`<button class="primary sm" data-redo="${p.id}" ${busy('voice')?'disabled':''}>🔁 Refazer voz desta frase</button>`:''}</div></div>`}).join('');
  b.innerHTML=h;
  b.querySelector('[data-a="trans"]')?.addEventListener('click',()=>startJob(`/api/projects/${PROJ.id}/translate`,{ids:null}));
  b.querySelector('[data-a="voiceall"]')?.addEventListener('click',()=>startJob(`/api/projects/${PROJ.id}/voice`,{ids:null}));
  b.querySelectorAll('[data-play]').forEach(e=>e.onclick=()=>{const p=ph.find(x=>x.id===e.dataset.play);playRange(p.s,p.s+(p.dur?p.dur/(p.rate||1):p.e-p.s))});
  b.querySelectorAll('[data-merge]').forEach(e=>e.onclick=async()=>{try{await flushSave();setProjectKeep(await api(`/api/projects/${PROJ.id}/phrases/${e.dataset.merge}/merge`,{method:'POST',json:{}}));renderTab()}catch(x){toast(x.message)}});
  b.querySelectorAll('[data-redo]').forEach(e=>e.onclick=()=>startJob(`/api/projects/${PROJ.id}/voice`,{ids:[e.dataset.redo]}));
  b.querySelectorAll('[data-spk]').forEach(e=>e.onchange=async()=>{try{await flushSave();setProjectKeep(await api(`/api/projects/${PROJ.id}/phrases/${e.dataset.spk}`,{method:'PUT',json:{speaker:e.value}}));renderTab()}catch(x){toast(x.message)}});
  b.querySelectorAll('[data-pt]').forEach(e=>e.onchange=async()=>{try{setProjectKeep(await api(`/api/projects/${PROJ.id}/phrases/${e.dataset.pt}`,{method:'PUT',json:{pt:e.value}}))}catch(x){toast(x.message)}});
  const timers={};
  b.querySelectorAll('[data-en]').forEach(e=>e.addEventListener('input',()=>{clearTimeout(timers[e.dataset.en]);timers[e.dataset.en]=setTimeout(async()=>{
    try{await flushSave();const r=await api(`/api/projects/${PROJ.id}/phrases/${e.dataset.en}`,{method:'PUT',json:{en:e.value}});setProjectKeep(r);updatePhraseBadges()}catch(x){toast(x.message)}},650)}));
}
function setProjectKeep(p){const sel=S.sel;PROJ=p;capCache={};prepareMedia();S.sel=sel;renderLayers();renderTimeline();renderTabs()}
function updatePhraseBadges(){
  for(const p of PROJ.phrases){const[st,cl]=statusOf(p);const bd=$('#bd_'+p.id);if(bd){bd.textContent=st;bd.className='badge '+cl}
    const a=$('#act_'+p.id);if(a){const need=stale().includes(p.id)&&p.en&&p.en.trim();const mg=a.querySelector('[data-merge]');a.querySelectorAll('[data-redo]').forEach(x=>x.remove());if(need){a.insertAdjacentHTML('beforeend',`<button class="primary sm" data-redo="${p.id}" ${busy('voice')?'disabled':''}>🔁 Refazer voz desta frase</button>`)}a.querySelector('[data-redo]')?.addEventListener('click',()=>startJob(`/api/projects/${PROJ.id}/voice`,{ids:[p.id]}))}}
  const va=$('#tabbody [data-a="voiceall"]');if(va){va.textContent=`Gerar voz (${stale().length} pendentes)`;va.disabled=!stale().length||busy('voice')}}

/* ---------- Vozes ---------- */
let playing=null;
function playUrl(rel){try{playing&&playing.pause()}catch(e){}playing=new Audio(mediaUrl(rel));playing.play().catch(()=>toast('Toque na tela e tente de novo.'))}
function tabVozes(b){
  const sp=PROJ.speakers||[],vs=PROJ.voices||[];
  let h=`<div class="ph"><span>Falantes (${sp.length})</span><button class="sm" data-a="addspk">+ Falante</button></div><div class="hint">Cada falante usa uma voz. Errou o número de pessoas? Refaça a identificação (rápido, não transcreve de novo; apaga as vozes já geradas):</div>
  <div class="btnrow"><select id="dzN" style="width:auto"><option value="">Automático</option>${[1,2,3,4,5,6].map(n=>`<option ${n===sp.length?'selected':''}>${n}</option>`).join('')}</select><button class="sm" id="dzGo" ${busy()?'disabled':''}>Refazer identificação</button></div>`;
  h+=sp.map(s=>`<div class="card"><h4><span><span class="sw" style="background:${s.color}"></span> <input type="text" data-spn="${s.id}" value="${esc(s.name)}" style="width:150px"></span>
    <select data-spv="${s.id}" style="width:auto">${vs.map(v=>`<option value="${v.id}" ${v.id===s.voice?'selected':''}>${esc(v.name)}</option>`).join('')}</select></h4></div>`).join('');
  h+=`<div class="ph"><span>Vozes (${vs.length})</span></div>`;
  h+=vs.map(v=>{const a=v.analysis||{},p=v.params;
    return`<div class="card" data-v="${v.id}"><h4><input type="text" data-vn="${v.id}" value="${esc(v.name)}" style="width:190px"><span class="badge">${v.engine}</span></h4>
    <div class="hint" style="padding:0">Tom detectado: <b>${a.label||'?'}</b>${a.f0?` · ${Math.round(a.f0)} Hz (faixa ${Math.round(a.p10)}–${Math.round(a.p90)} Hz)`:''} · amostra de ${a.seconds||'?'}s</div>
    <audio controls preload="none" src="${mediaUrl(v.ref)}"></audio>
    ${rng(v.id,'speed','Velocidade',.7,1.4,.01,p.speed)}${rng(v.id,'temperature','Expressividade (variação)',.1,1,.01,p.temperature)}${rng(v.id,'pitch','Tom (semitons)',-6,6,.1,p.pitch)}${rng(v.id,'gain','Volume',.5,1.5,.01,p.gain)}
    <label class="chk" style="padding:2px 0"><input type="checkbox" data-auto="${v.id}" ${p.auto_pitch?'checked':''}> Igualar o tom ao da voz original automaticamente</label>
    <div class="row2" style="flex-wrap:wrap"><button class="sm" data-prev="${v.id}" ${busy()?'disabled':''}>▶ Ouvir amostra</button><button class="sm" data-cal="${v.id}" ${busy()?'disabled':''}>🎚 Calibrar tom</button></div>
    <div class="hint" style="padding:0">Ao mudar os controles as frases deste falante ficam desatualizadas: refaça a voz na aba Frases.</div></div>`}).join('');
  h+=`<div class="card"><h4>Enviar áudio de referência</h4><div class="hint" style="padding:0">Mande 10–25 s de uma voz limpa (sem música). O app mede o tom e cria uma voz nova para usar nos falantes.</div>
    <input type="text" id="nvName" placeholder="Nome da voz" value="Voz nova"><input type="file" id="nvFile" accept="audio/*,video/*"><button class="sm primary" id="nvGo">Analisar e criar voz</button></div>`;
  b.innerHTML=h;
  $('#dzGo').onclick=()=>startJob(`/api/projects/${PROJ.id}/diarize`,{n_speakers:$('#dzN').value?+$('#dzN').value:null});
  b.querySelector('[data-a="addspk"]').onclick=async()=>{try{setProjectKeep(await api(`/api/projects/${PROJ.id}/speakers`,{method:'POST',json:{}}));renderTab()}catch(e){toast(e.message)}};
  b.querySelectorAll('[data-spn]').forEach(e=>e.onchange=async()=>{setProjectKeep(await api(`/api/projects/${PROJ.id}/speakers/${e.dataset.spn}`,{method:'PUT',json:{name:e.value}}))});
  b.querySelectorAll('[data-spv]').forEach(e=>e.onchange=async()=>{setProjectKeep(await api(`/api/projects/${PROJ.id}/speakers/${e.dataset.spv}`,{method:'PUT',json:{voice:e.value}}));renderTab()});
  b.querySelectorAll('[data-vn]').forEach(e=>e.onchange=async()=>{setProjectKeep(await api(`/api/projects/${PROJ.id}/voices/${e.dataset.vn}`,{method:'PUT',json:{name:e.value}}));renderTab()});
  const t={};b.querySelectorAll('[data-vp]').forEach(e=>e.addEventListener('input',()=>{const[vid,k]=e.dataset.vp.split('|');e.previousElementSibling.querySelector('output').textContent=(+e.value).toFixed(2);
    clearTimeout(t[e.dataset.vp]);t[e.dataset.vp]=setTimeout(async()=>{try{setProjectKeep(await api(`/api/projects/${PROJ.id}/voices/${vid}`,{method:'PUT',json:{params:{[k]:+e.value}}}))}catch(x){toast(x.message)}},500)}));
  b.querySelectorAll('[data-auto]').forEach(e=>e.onchange=async()=>{setProjectKeep(await api(`/api/projects/${PROJ.id}/voices/${e.dataset.auto}`,{method:'PUT',json:{params:{auto_pitch:e.checked}}}))});
  b.querySelectorAll('[data-prev]').forEach(e=>e.onclick=async()=>{const j=await startJob(`/api/projects/${PROJ.id}/voices/${e.dataset.prev}/preview`,{});if(!j)return;const r=await jobDone(j.id);if(r.status==='pronto')playUrl(r.result.file);else toast(r.error)});
  b.querySelectorAll('[data-cal]').forEach(e=>e.onclick=async()=>{const j=await startJob(`/api/projects/${PROJ.id}/voices/${e.dataset.cal}/calibrate`,{});if(!j)return;const r=await jobDone(j.id);if(r.status==='pronto'){toast(`Tom ajustado em ${r.result.pitch>0?'+':''}${r.result.pitch} semitons. Ouça a amostra.`);await reloadProject();}else toast(r.error)});
  $('#nvGo').onclick=async()=>{const f=$('#nvFile').files[0];if(!f)return toast('Escolha um arquivo de áudio.');const fd=new FormData();fd.append('name',$('#nvName').value||'Voz nova');fd.append('file',f);
    $('#nvGo').disabled=true;try{await api(`/api/projects/${PROJ.id}/voices`,{method:'POST',body:fd});await reloadProject();toast('Voz criada. Atribua-a a um falante acima.')}catch(e){toast(e.message)}finally{$('#nvGo').disabled=false}};
}
function rng(vid,k,label,mn,mx,st,v){return`<div class="fld" style="padding:2px 0"><label>${label}<output>${(+v).toFixed(2)}</output></label><input type="range" data-vp="${vid}|${k}" min="${mn}" max="${mx}" step="${st}" value="${v}"></div>`}

/* ---------- Lip-sync ---------- */
let LSSEL=null;
function tabLipsync(b){
  const spans=(PROJ.lipsync||{}).spans||[];
  let h=`<div class="hint">Corrige o movimento da boca para combinar com a voz em inglês. O app acha os trechos em que um rosto fala, e você pode <b>mover/redimensionar a caixa</b> no vídeo, mudar a força ou <b>desligar</b> um trecho. Cada trecho é refeito sozinho.</div>
  <div class="hint warn">Aviso honesto: o motor grátis (Wav2Lip) funciona melhor em planos fechados e em rostos grandes. Em plano aberto, desligue o trecho se ficar estranho.</div>
  <div class="btnrow"><button data-a="sug" ${busy()?'disabled':''}>Achar trechos com rosto falando</button><button class="primary" data-a="runall" ${spans.length&&!busy()?'':'disabled'}>Sincronizar todos os trechos ligados</button></div>`;
  h+=spans.map(s=>{const sp=spk(s.speaker)||{name:s.speaker,color:'#888'};
    return`<div class="card" data-sp="${s.id}" style="${s.id===LSSEL?'border-color:var(--accent)':''}"><h4><span><span class="sw" style="background:${sp.color}"></span> ${esc(sp.name)} · ${fmt(s.s)}–${fmt(s.e)}</span><span class="badge ${s.status==='done'?'ok':'stale'}">${s.status==='done'?'pronto':'a fazer'}</span></h4>
    <div class="hint" style="padding:0">Rosto: ${s.face_px||'?'} px de largura${s.warn?`<br><span style="color:var(--warn)">${esc(s.warn)}</span>`:''}</div>
    <label class="chk" style="padding:0"><input type="checkbox" data-en="${s.id}" ${s.enabled?'checked':''}> Ligado</label>
    <div class="fld" style="padding:0"><label>Força<output>${(+s.strength).toFixed(2)}</output></label><input type="range" data-str="${s.id}" min="0" max="1" step="0.05" value="${s.strength}"></div>
    <div class="row2"><button class="sm" data-sel="${s.id}">Editar caixa no vídeo</button><button class="sm" data-seek="${s.id}">▶ Ver</button><button class="sm primary" data-one="${s.id}" ${busy()?'disabled':''}>Refazer este trecho</button></div></div>`}).join('')||'<div class="hint">Nenhum trecho ainda. Clique em “Achar trechos com rosto falando” (a voz em inglês precisa estar gerada).</div>';
  b.innerHTML=h;
  b.querySelector('[data-a="sug"]').onclick=()=>startJob(`/api/projects/${PROJ.id}/lipsync/suggest`,{});
  b.querySelector('[data-a="runall"]').onclick=()=>startJob(`/api/projects/${PROJ.id}/lipsync/run`,{ids:null});
  const patch=async(id,body)=>{try{setProjectKeep(await api(`/api/projects/${PROJ.id}/lipsync/spans/${id}`,{method:'PUT',json:body}));renderTab()}catch(e){toast(e.message)}};
  b.querySelectorAll('[data-en]').forEach(e=>e.onchange=()=>patch(e.dataset.en,{enabled:e.checked}));
  b.querySelectorAll('[data-str]').forEach(e=>e.onchange=()=>patch(e.dataset.str,{strength:+e.value}));
  b.querySelectorAll('[data-sel]').forEach(e=>e.onclick=()=>{LSSEL=e.dataset.sel;const s=spans.find(x=>x.id===LSSEL);seek(s.s+.2);renderTab()});
  b.querySelectorAll('[data-seek]').forEach(e=>e.onclick=()=>{const s=spans.find(x=>x.id===e.dataset.seek);playRange(s.s,s.e)});
  b.querySelectorAll('[data-one]').forEach(e=>e.onclick=()=>startJob(`/api/projects/${PROJ.id}/lipsync/run`,{ids:[e.dataset.one]}));
}
/* caixa de edição do rosto sobre o preview */
S.hook.lsbox=()=>{
  const box=$('#lsbox');const s=TAB==='lipsync'&&LSSEL&&((PROJ.lipsync||{}).spans||[]).find(x=>x.id===LSSEL);
  if(!s||!PROJ.native){box.hidden=true;return}
  const [nw,nh]=PROJ.native,sc=Math.max(W/nw,H/nh),ox=(W-nw*sc)/2,oy=(H-nh*sc)/2,r=s.rect;
  box.hidden=false;box.innerHTML='<i></i>';
  const place=()=>{box.style.left=((r.x*sc+ox)/W*100)+'%';box.style.top=((r.y*sc+oy)/H*100)+'%';box.style.width=(r.w*sc/W*100)+'%';box.style.height=(r.h*sc/H*100)+'%'};place();
  const wrap=box.parentElement;
  const drag=(mode)=>e=>{e.preventDefault();e.stopPropagation();const rc=wrap.getBoundingClientRect(),x0=e.clientX,y0=e.clientY,o={...r};box.setPointerCapture(e.pointerId);
    const mv=ev=>{const dx=(ev.clientX-x0)/rc.width*W/sc,dy=(ev.clientY-y0)/rc.height*H/sc;
      if(mode==='move'){r.x=clamp(Math.round(o.x+dx),0,nw-r.w);r.y=clamp(Math.round(o.y+dy),0,nh-r.h)}else{const d=Math.max(dx,dy);r.w=r.h=clamp(Math.round(o.w+d),48,Math.min(nw-r.x,nh-r.y))}place()};
    const up=async()=>{box.removeEventListener('pointermove',mv);box.removeEventListener('pointerup',up);try{await api(`/api/projects/${PROJ.id}/lipsync/spans/${s.id}`,{method:'PUT',json:{rect:{x:r.x,y:r.y,w:r.w,h:r.h}}});s.status='todo';renderTab();toast('Caixa ajustada. Clique em “Refazer este trecho”.')}catch(x){toast(x.message)}};
    box.addEventListener('pointermove',mv);box.addEventListener('pointerup',up)};
  box.onpointerdown=drag('move');box.querySelector('i').onpointerdown=drag('size');
};

/* ---------- Áudio ---------- */
function tabAudio(b){
  const m=PROJ.mix||{voice:1,background:.9,original:0};
  const row=(k,label,mx)=>`<div class="fld"><label>${label}<output>${(+m[k]).toFixed(2)}</output></label><input type="range" data-mix="${k}" min="0" max="${mx}" step="0.05" value="${m[k]}"></div>`;
  b.innerHTML=`<div class="hint">${PROJ.has_separation?'✔ A voz original foi separada do som de fundo (Demucs). O fundo mantém música e ambiente; a voz em português fica de fora.':'A separação voz/fundo não rodou neste projeto.'}</div>
   ${row('voice','Voz dublada em inglês',1.5)}${row('background','Fundo (sem a voz original)',1.5)}${row('original','Áudio original (com a voz em português)',1)}
   <div class="hint" style="padding-top:0">Se o fundo soar “vazio” nos trechos de fala (a separação nunca é perfeita), suba o fundo um pouco ou envie uma trilha sua como camada de áudio.</div>
   <label class="chk"><input type="checkbox" id="cvr" ${PROJ.cover_old_subs?'checked':''}> Cobrir legendas antigas gravadas no vídeo (vidro)</label>
   <div class="ph"><span>Pronúncia</span></div><div class="hint">Uma por linha: <code>escrita = como falar</code>. Ex.: <code>DoorMaxx = Doormax</code>. Depois refaça as vozes afetadas.</div>
   <div class="fld"><textarea id="pron" rows="4">${esc(Object.entries(PROJ.pronounce||{}).map(([a,c])=>`${a} = ${c}`).join('\n'))}</textarea></div>`;
  b.querySelectorAll('[data-mix]').forEach(e=>e.addEventListener('input',()=>{const k=e.dataset.mix;PROJ.mix[k]=+e.value;e.previousElementSibling.querySelector('output').textContent=(+e.value).toFixed(2);
    for(const l of LAY()){if(!l.auto)continue;if(k==='voice'&&l.phrase)l.volume=+e.value;if(k==='background'&&l.id==='bg')l.volume=+e.value;if(k==='original'&&l.id==='vid')l.volume=+e.value}saveLayersSoon()}));
  $('#cvr').onchange=async e=>{PROJ.cover_old_subs=e.target.checked;await flushSave();await api(`/api/projects/${PROJ.id}/phrases/${PROJ.phrases[0]?.id||'p1'}`,{method:'PUT',json:{}}).catch(()=>{});await reloadProject()};
  $('#pron').onchange=async e=>{const d={};for(const ln of e.target.value.split('\n')){const[a,c]=ln.split('=').map(s=>s&&s.trim());if(a&&c)d[a]=c}PROJ.pronounce=d;await flushSave();await reloadProject();toast('Pronúncia salva. Refaça as vozes afetadas.')};
}

/* ---------- Saída ---------- */
async function tabSaida(b){
  let renders=[];try{renders=await api(`/api/projects/${PROJ.id}/renders`)}catch(e){}
  const h264=codecInfo();
  b.innerHTML=`<div class="fld"><label>Qualidade do vídeo final</label><select id="rsc"><option value="0.5">540×960 (rápido)</option><option value="0.75" selected>810×1440 (recomendado)</option><option value="1">1080×1920 (máxima, demora mais)</option></select></div>
   <div class="btnrow"><button class="primary" data-a="render" ${busy()?'disabled':''}>Renderizar vídeo (MP4 H.264)</button></div>
   <div class="hint">O vídeo é montado no computador onde o servidor roda, em MP4 H.264 (abre no celular, Instagram e WhatsApp). Você pode fechar esta aba: o arquivo fica aqui embaixo quando terminar.</div>
   <div class="ph"><span>Vídeos prontos</span></div>
   ${renders.map(r=>`<div class="card"><h4>${esc(r.name)}<span class="badge">${(r.size/1048576).toFixed(1)} MB</span></h4><video class="pv" controls preload="metadata" src="${mediaUrl('render/'+r.name)}"></video><a class="dl" download="${esc(PROJ.name)}-${esc(r.name)}" href="${mediaUrl('render/'+r.name)}">Baixar arquivo</a></div>`).join('')||'<div class="hint">Nenhum vídeo renderizado ainda.</div>'}
   <div class="ph"><span>Diagnóstico do navegador</span></div><div class="hint">${h264}</div>`;
  b.querySelector('[data-a="render"]').onclick=()=>startJob(`/api/projects/${PROJ.id}/render`,{scale:+$('#rsc').value,crf:18});
}
function codecInfo(){
  const ms=window.MediaSource&&MediaSource.isTypeSupported('video/mp4; codecs="avc1.640028, mp4a.40.2"');
  const v=document.createElement('video').canPlayType('video/mp4; codecs="avc1.640028"');
  return `H.264 neste navegador: <b>${(ms||v)?'sim ✔':'não ✘'}</b>. ${(ms||v)?'O vídeo e os arquivos .mp4 tocam normalmente.':'Este navegador não toca H.264: use o Chrome oficial (google.com/chrome), não o Chromium.'} O servidor sempre gera o MP4 por conta própria, então isto só afeta o preview.`}
