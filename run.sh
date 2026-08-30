#!/usr/bin/env bash
# Convenience launcher: creates a venv on first run, installs deps,
# fetches the law text if missing, and starts the server.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate

pip install -q -r requirements.txt

if [ ! -f "data/betrvg.json" ]; then
  echo "Fetching BetrVG text from gesetze-im-internet.de..."
  python scripts/fetch_betrvg.py
fi

if [ ! -f "data/bdsg.json" ]; then
  echo "Fetching BDSG text from gesetze-im-internet.de..."
  python scripts/fetch_bdsg.py
fi

if [ ! -f ".env" ]; then
  echo "No .env found - copying .env.example. Edit .env and add at least one free API key before asking questions."
  cp .env.example .env
fi

echo "Starting server at http://127.0.0.1:8000 ..."
uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
