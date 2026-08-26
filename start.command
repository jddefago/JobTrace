#!/bin/bash
# macOS equivalent of start.bat. Double-click in Finder, or run ./start.command
# from Terminal. Starts the server in the background and opens the dashboard.
set -u
cd "$(dirname "$0")"

# Identify THIS install's own server.py by its absolute path, not just
# "backend/server.py" -- that fragment is identical across every copy of
# JobTrace on the machine, so a relative-path match could mistake a
# different install's already-running server for this one.
SCRIPTPATH="$(pwd)/backend/server.py"

# Avoid launching a second server if this install's own one is already running.
if pgrep -f "$SCRIPTPATH" >/dev/null 2>&1; then
    open "http://localhost:8766"
    exit 0
fi

PYEXE=""
if command -v python3 >/dev/null 2>&1; then
    PYEXE="python3"
elif command -v python >/dev/null 2>&1; then
    PYEXE="python"
fi

if [ -z "$PYEXE" ]; then
    echo ""
    echo "Python was not found on your PATH."
    echo "Please install Python 3.10 or later from https://www.python.org/downloads/"
    echo ""
    read -r -p "Press Enter to close..." _
    exit 1
fi

mkdir -p data

nohup "$PYEXE" "$SCRIPTPATH" > data/server.log 2>&1 &
disown

sleep 2
open "http://localhost:8766"
exit 0
