#!/usr/bin/env bash
# Start review web UI at http://127.0.0.1:8010
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
( sleep 2; python -m webbrowser "http://127.0.0.1:8010" >/dev/null 2>&1 ) &
python -m app.cli serve
