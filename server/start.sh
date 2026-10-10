#!/usr/bin/env bash
cd "$(dirname "$0")/.."
exec server/.venv/bin/python -m server.run
