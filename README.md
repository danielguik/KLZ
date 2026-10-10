# KLZ Studio — dublagem e edição de vídeo por camadas

## KLZ Studio (servidor) — a versão completa
Roda no **seu computador** (faz o trabalho pesado) e abre no **navegador do computador e do celular**.

```
git clone https://github.com/danielguik/klz.git && cd klz
git checkout claude/affectionate-albattani-1ny0vj
bash server/install.sh        # 1ª vez: instala tudo (baixa vários GB de modelos)
bash server/start.sh          # no Mac também: dois cliques em server/start.command
```
O terminal mostra os endereços e a senha (`token=…`). **Celular:** mesmo Wi-Fi, abra o endereço "No celular" (ou o botão 📱 Celular na tela, que mostra um QR code). Fora de casa: instale o Tailscale (grátis) no computador e no celular.

**O que ele faz** (cada passo é editável na tela):
- **Analisar vídeo:** separa a voz do som de fundo (Demucs), transcreve (Whisper), identifica quantas pessoas falam e quem fala cada frase.
- **Frases:** tradução editável frase a frase. Mudou o inglês? Aparece o botão **Refazer voz desta frase** (só ela é refeita). Dá para juntar frases, trocar o falante e ver quando o inglês passa do tempo da fala original.
- **Vozes:** 1 voz por falante (vários falantes por vídeo). Envie um áudio de referência: o app mede o tom (Hz) e clona a voz. Controles de velocidade, expressividade, tom (semitons) e volume; "Calibrar tom" iguala ao tom original.
- **Lip-sync:** acha os trechos com um rosto falando; você move/redimensiona a caixa no vídeo, muda a força ou desliga, e refaz só aquele trecho.
- **Áudio:** mixagem voz dublada / fundo sem a voz / original; pronúncia de marcas; cobrir legendas antigas com vidro.
- **Saída:** renderiza MP4 H.264 no computador (Remotion) e deixa o arquivo disponível para baixar do celular.

**Chaves opcionais** (variáveis de ambiente no computador): `ANTHROPIC_API_KEY` liga a tradução automática; `ELEVENLABS_API_KEY` permite voz de qualidade profissional.

**Limites honestos:** lip-sync grátis (Wav2Lip) só funciona bem com rostos grandes (≥ ~80 px); a voz grátis (XTTS) é só para uso não comercial e ainda soa de IA; a separação voz/fundo nunca é perfeita. Windows: use WSL2.

---

## (versões anteriores)

- **Painel estilo After Effects** (`web/index.html`): projeto, efeitos por categoria, viewer, controles de efeito com sliders, timeline com camadas arrastáveis, playhead, corte.
- **Agente** (Claude + ferramentas): "corta os 3 primeiros segundos, põe vinheta e legenda" — edita o mesmo JSON que o painel.
- **Dublagem** PT→EN: Whisper → tradução por intenção (Claude) → voz (ElevenLabs com clonagem, ou OpenAI TTS) → ajuste de tempo → camadas de áudio.
- **Render**: tudo vira um comando FFmpeg (`klz/render.py`).

## Studio (editor por camadas, estilo dos vídeos de referência)
`studio/` é um projeto Remotion: timeline com camadas nomeadas, preview, painel de propriedades editável (cor, tempo, texto, legendas palavra a palavra, vidro, título, número animado, zoom, volume) e botão Render.
```
cd studio && npm install && npm start      # abre o Studio em http://localhost:3000
# pipeline (Python): transcrever -> traduzir -> voz -> projeto
python -m klz.make_project projects/<pasta> <nome> --voz dub      # gera studio/src/Root.tsx + assets em studio/public/
```
Edite no Studio e clique em Save: grava no `Root.tsx`. Render final: `npm run render`.

## Rodar (versão antiga, FFmpeg)
```
pip install -r requirements.txt   # + ffmpeg instalado
export ANTHROPIC_API_KEY=... ELEVENLABS_API_KEY=... OPENAI_API_KEY=...
uvicorn klz.server:app --port 8000   # abra http://localhost:8000
```
Novo efeito = uma entrada em `klz/effects.py` (aparece sozinho no painel e para o agente).

## Limitações
- Prévia = render FFmpeg em meia resolução (não é tempo real como no After Effects).
- Dublagem e agente exigem chaves de API e **não foram testados de ponta a ponta** (sem chaves); render e UI foram testados.
- Sem lip-sync de rosto ainda (ex.: integrar VideoReTalking/Wav2Lip em `dubbing.py`).

## Rodar o Studio na sua máquina (passo a passo)
```
git clone https://github.com/danielguik/klz.git && cd klz
git checkout claude/affectionate-albattani-1ny0vj
cp "SEU_VIDEO.mp4" studio/public/door/original.mp4     # o vídeo original NÃO está no Git
cd studio && npm install && npm start                   # abre http://localhost:3000 (composição "Reel")
```
Precisa de Node 18+. Os áudios da dublagem (`studio/public/door/dub_*.wav`) já vêm no repositório.

## App web (KLZ Editor) — sem instalar nada
`app/klz-editor.html` é um editor de arquivo único (preview, timeline, camadas, edição da tradução, exportação de vídeo). Fonte: `app/template.html`; montar com `python -m klz.build_app`. Abra o vídeo original dentro do app (ele não vai embutido). Use o Chrome no computador.
