#!/bin/bash
# macOS/Linux scheduled-task runner for the headless Gmail sync
# (backend/gmail_api_sync.py). Meant to be invoked by launchd/cron (see
# com.jobtrace.gmailsync.plist.example), not double-clicked.
#
# Unlike run_gmail_sync_claude.sh/run_gmail_sync_codex.sh, this needs no AI
# assistant app installed -- only Python and the dependencies in
# requirements.txt, plus the one-time setup in GMAIL_SYNC_API.md (a Google
# OAuth client + an Anthropic API key). Run this once manually first so the
# Gmail OAuth consent screen can be completed interactively; after that the
# cached token lets it run fully unattended.
set -u
cd "$(dirname "$0")"

PYEXE="python3"
command -v python3 >/dev/null 2>&1 || PYEXE="python"

TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p data/sync_logs
LOGFILE="data/sync_logs/gmail_sync_api_task_${TS}.log"

{
    echo "===== Gmail API sync run started $(date) ====="
    "$PYEXE" backend/gmail_api_sync.py
    echo "===== Gmail API sync run finished $(date) ====="
} >> "$LOGFILE" 2>&1
