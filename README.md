# KLZ — Editor de vídeo com agente + dublagem PT→EN

- **Painel estilo After Effects** (`web/index.html`): projeto, efeitos por categoria, viewer, controles de efeito com sliders, timeline com camadas arrastáveis, playhead, corte.
- **Agente** (Claude + ferramentas): "corta os 3 primeiros segundos, põe vinheta e legenda" — edita o mesmo JSON que o painel.
- **Dublagem** PT→EN: Whisper → tradução por intenção (Claude) → voz (ElevenLabs com clonagem, ou OpenAI TTS) → ajuste de tempo → camadas de áudio.
- **Render**: tudo vira um comando FFmpeg (`klz/render.py`).

## Rodar
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
