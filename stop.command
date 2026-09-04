#!/bin/bash
# macOS equivalent of stop.bat. Double-click in Finder, or run ./stop.command
# from Terminal.
set -u
cd "$(dirname "$0")"

# Match THIS install's own server.py by absolute path -- see start.command's
# comment. A relative-path match would risk stopping a different JobTrace
# install's server instead of (or as well as) this one.
SCRIPTPATH="$(pwd)/backend/server.py"

echo "Stopping JobTrace..."

PIDS="$(pgrep -f "$SCRIPTPATH" || true)"
if [ -n "$PIDS" ]; then
    kill $PIDS
    echo "JobTrace server stopped."
else
    echo "JobTrace was not running."
fi

read -r -p "Press Enter to close..." _
