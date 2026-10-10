"use strict";
/* Cola: login, projetos, fila de tarefas, celular (QR). */
async function reloadProject(){if(!API.pid)return;try{await flushSave();const p=await api(`/api/projects/${API.pid}`);setProject(p);renderTab()}catch(e){toast(e.message)}}
let lastErr=null,pollT=null;
async function pollJobs(){
  if(!API.pid)return;
  let list=[];try{list=await api(`/api/projects/${API.pid}/jobs`)}catch(e){return}
  const prev=JOBS;JOBS=list;
  const active=list.find(j=>j.status==='rodando'||j.status==='na fila');
  const chip=$('#jobchip');
  if(active){chip.hidden=false;chip.className='chip run';chip.textContent='⏳ '+active.label+(active.progress?' — '+active.progress:'')}
  else if(lastErr){chip.hidden=false;chip.className='chip err';chip.textContent='✘ '+lastErr}
  else chip.hidden=true;
  for(const j of list){const o=prev.find(x=>x.id===j.id);
    if(o&&(o.status==='rodando'||o.status==='na fila')&&(j.status==='pronto'||j.status==='erro')){
      if(j.status==='erro'){lastErr=j.label+': '+j.error;toast('Erro: '+j.error,7000)}else{lastErr=null;toast('Pronto: '+j.label)}
      await reloadProject();
    }}
  clearTimeout(pollT);pollT=setTimeout(pollJobs,active?1500:6000);
}
S.hook.trackJobs=()=>{setTimeout(pollJobs,300)};

/* ---------- login ---------- */
function loginBox(msg){
  return new Promise(res=>{const o=$('#ovl');o.hidden=false;
    o.innerHTML=`<div class="box"><h3>KLZ Studio</h3><div class="hint" style="padding:0">${esc(msg||'Digite a senha de acesso. Ela aparece no terminal onde o servidor foi iniciado (depois de “token=”).')}</div><input type="password" id="lgp" placeholder="Senha"><button class="primary" id="lgb">Entrar</button></div>`;
    const go=()=>{o.hidden=true;res($('#lgp').value.trim())};$('#lgb').onclick=go;$('#lgp').onkeydown=e=>{if(e.key==='Enter')go()};$('#lgp').focus()})
}
async function auth(){
  const u=new URL(location.href),t=u.searchParams.get('token');
  if(t){API.token=t;localStorage.setItem('klz-token',t);u.searchParams.delete('token');history.replaceState(null,'',u.pathname+u.search)}
  for(;;){try{CAPS=await api('/api/capabilities');return}catch(e){if(e.code!==401){toast('Não consegui falar com o servidor: '+e.message);throw e}
    API.token=await loginBox(API.token?'Senha incorreta. Tente de novo.':'');localStorage.setItem('klz-token',API.token)}}
}

/* ---------- projetos ---------- */
async function refreshProjects(sel){
  const list=await api('/api/projects');const s=$('#selProj');
  s.innerHTML=list.map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')||'<option value="">(nenhum projeto)</option>';
  const want=sel||localStorage.getItem('klz-last')||(list[0]&&list[0].id);
  if(want&&list.find(p=>p.id===want)){s.value=want;await openProject(want)}else{PROJ=null;API.pid=null;renderAll();renderTab()}
}
async function openProject(id){API.pid=id;localStorage.setItem('klz-last',id);const p=await api(`/api/projects/${id}`);setProject(p);if(p.phrases&&p.phrases.length)TAB=TAB==='camada'?'camada':'frases';renderTab();pollJobs()}
$('#selProj').onchange=e=>e.target.value&&openProject(e.target.value);

function newProjectBox(){
  const o=$('#ovl');o.hidden=false;
  o.innerHTML=`<div class="box"><h3>Novo projeto</h3>
   <input type="text" id="npName" placeholder="Nome do projeto" value="Meu vídeo">
   <label class="hint" style="padding:0">Vídeo original (o que será dublado)</label><input type="file" id="npFile" accept="video/*">
   <div class="hint" style="padding:0">Idioma da fala original</div><select id="npLang"><option value="pt">Português</option><option value="en">Inglês</option><option value="es">Espanhol</option></select>
   <div class="hint" style="padding:0">Quantas pessoas falam? (deixe em automático se não souber)</div><select id="npN"><option value="">Automático</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option><option>6</option></select>
   <div class="hint" style="padding:0">Nomes/marcas que aparecem (ajuda a transcrever certo)</div><input type="text" id="npGl" placeholder="Ex.: Hopedale, DoorMaxx, Fast Shapes">
   <div class="bar" id="npBar" hidden><i></i></div><div class="hint" id="npMsg" style="padding:0"></div>
   <div class="row2"><button id="npCancel" class="ghost">Cancelar</button><span style="flex:1"></span><button id="npGo" class="primary">Enviar e analisar</button></div></div>`;
  $('#npCancel').onclick=()=>o.hidden=true;
  $('#npGo').onclick=async()=>{
    const f=$('#npFile').files[0];if(!f)return $('#npMsg').textContent='Escolha o vídeo.';
    $('#npGo').disabled=true;$('#npBar').hidden=false;
    try{
      const p=await api('/api/projects',{method:'POST',json:{name:$('#npName').value||'Meu vídeo'}});
      await new Promise((ok,bad)=>{const x=new XMLHttpRequest();x.open('POST',`/api/projects/${p.id}/upload`);x.setRequestHeader('X-KLZ-Token',API.token);
        x.upload.onprogress=e=>{$('#npBar i').style.width=(e.loaded/e.total*100)+'%';$('#npMsg').textContent='Enviando… '+Math.round(e.loaded/e.total*100)+'%'};
        x.onload=()=>x.status<300?ok():bad(new Error('Falha no envio ('+x.status+')'));x.onerror=()=>bad(new Error('Falha no envio'));const fd=new FormData();fd.append('file',f);x.send(fd)});
      await api(`/api/projects/${p.id}/ingest`,{method:'POST',json:{language:$('#npLang').value,n_speakers:$('#npN').value?+$('#npN').value:null,glossary:$('#npGl').value}});
      o.hidden=true;await refreshProjects(p.id);toast('Analisando o vídeo. Isso leva alguns minutos; você pode acompanhar no topo.',6000);pollJobs();
    }catch(e){$('#npMsg').textContent=e.message;$('#npGo').disabled=false}
  };
}
$('#bNew').onclick=newProjectBox;

/* ---------- celular ---------- */
$('#bPhone').onclick=async()=>{
  const o=$('#ovl');o.hidden=false;o.innerHTML='<div class="box"><h3>Abrir no celular</h3><div class="hint" style="padding:0">Carregando…</div></div>';
  try{const i=await api('/api/info');const urls=i.ips.map(ip=>`http://${ip}:${i.port}/?token=${i.token}`);
    o.innerHTML=`<div class="box"><h3>Abrir no celular</h3>
     <div class="hint" style="padding:0">1) Conecte o celular no <b>mesmo Wi-Fi</b> do computador. 2) Aponte a câmera para o QR code (ou digite o endereço). O celular edita e vê os vídeos prontos; quem trabalha pesado é o computador.</div>
     ${urls.map(u=>`<div style="text-align:center"><img alt="QR" style="width:200px;background:#fff;padding:8px;border-radius:8px" src="/api/qr.svg?text=${encodeURIComponent(u)}&token=${encodeURIComponent(API.token)}"><div style="font:12px var(--mono);word-break:break-all">${esc(u)}</div></div>`).join('')||'<div class="hint warn">Não achei o endereço do computador na rede. Veja o terminal onde o servidor está rodando.</div>'}
     <div class="hint" style="padding:0">Fora de casa? Instale o <b>Tailscale</b> no computador e no celular (grátis) e use o endereço 100.x.x.x do computador no lugar do IP acima. A senha protege o acesso: não compartilhe o link.</div>
     <button class="primary" id="phOk">Fechar</button></div>`;$('#phOk').onclick=()=>o.hidden=true}
  catch(e){o.innerHTML=`<div class="box"><h3>Celular</h3><div class="hint">${esc(e.message)}</div><button id="phOk">Fechar</button></div>`;$('#phOk').onclick=()=>o.hidden=true}
};
$('#bRender').onclick=()=>{TAB='saida';renderTab();document.querySelector('[data-a="render"]')?.scrollIntoView()};

/* ---------- formulário de análise para projeto com vídeo já enviado ---------- */
function analyzeForm(){
  return `<div class="card"><h4>Analisar vídeo</h4><div class="hint" style="padding:0">Separa a voz do fundo, transcreve e identifica quem fala. Leva alguns minutos.</div>
  <select id="anLang"><option value="pt">Falado em português</option><option value="en">Falado em inglês</option><option value="es">Falado em espanhol</option></select>
  <input type="text" id="anGl" placeholder="Nomes/marcas (ajuda a transcrever)"><button class="primary" id="anGo" ${PROJ&&PROJ.media?'':'disabled'}>Analisar vídeo</button></div>`}
S.hook.analyze=()=>{const b=$('#anGo');if(b)b.onclick=()=>startJob(`/api/projects/${PROJ.id}/ingest`,{language:$('#anLang').value,n_speakers:null,glossary:$('#anGl').value})};

/* ---------- início ---------- */
(async function(){
  buildAdd();renderAll();renderTab();
  try{await document.fonts.load('800 64px Manrope')}catch(e){}
  try{await auth();await refreshProjects();if(!PROJ)newProjectBox()}catch(e){}
})();
