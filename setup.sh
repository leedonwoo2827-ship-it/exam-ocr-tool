#!/usr/bin/env bash
# First-time setup: create venv and install dependencies
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo
echo "[DONE] Setup complete. Now run: ./run.sh"
