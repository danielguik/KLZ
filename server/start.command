#!/usr/bin/env bash
# macOS: dê dois cliques neste arquivo para iniciar o KLZ Studio.
cd "$(dirname "$0")/.."
exec server/.venv/bin/python -m server.run
