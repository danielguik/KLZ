#!/usr/bin/env bash
# Instala o KLZ Studio neste computador (macOS ou Linux). Uso: bash server/install.sh
set -e
cd "$(dirname "$0")/.."
echo "== KLZ Studio: instalação =="

need() { command -v "$1" >/dev/null 2>&1; }
if ! need ffmpeg; then
  if need brew; then brew install ffmpeg; else echo "Instale o ffmpeg (https://ffmpeg.org) e rode de novo."; exit 1; fi
fi
if ! need node; then
  if need brew; then brew install node; else echo "Instale o Node.js 18+ (https://nodejs.org) e rode de novo."; exit 1; fi
fi
if ! need git; then echo "Instale o git e rode de novo."; exit 1; fi
if ! need uv; then curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"; fi

echo "== Python 3.11 + dependências (baixa vários GB na primeira vez) =="
uv venv --python 3.11 server/.venv
if [ "$(uname -s)" = "Linux" ]; then EXTRA="--extra-index-url https://download.pytorch.org/whl/cpu"; else EXTRA=""; fi
uv pip install --python server/.venv/bin/python -r server/requirements.txt $EXTRA
# o coqui-tts exige transformers 4.x; o resolver às vezes sobe de versão
uv pip install --python server/.venv/bin/python "transformers==4.57.1"

echo "== Editor/renderizador de vídeo (Remotion) =="
(cd studio && npm install --no-audit --no-fund)

echo "== Pronto =="
echo "Para iniciar:  bash server/start.sh"
