#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3.12 and run this file again."
  read -r -p "Press Enter to close..."
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 20+ and npm are required. Install Node.js and run this file again."
  read -r -p "Press Enter to close..."
  exit 1
fi
BACKEND="cd \"$ROOT/backend\" && if [ ! -d .venv ]; then python3 -m venv .venv; fi && source .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements.txt && uvicorn app.main:app --reload"
FRONTEND="cd \"$ROOT/frontend\" && npm install && npm run dev"
osascript <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "$BACKEND"
  delay 2
  do script "$FRONTEND"
end tell
APPLESCRIPT
