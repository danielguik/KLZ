# KLZ — Editor de vídeo com agente + dublagem PT→EN

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
