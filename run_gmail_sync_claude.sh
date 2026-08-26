#!/bin/bash
# macOS/Linux equivalent of run_gmail_sync_claude.bat. Meant to be invoked by
# launchd/cron (see com.jobtrace.gmailsync.plist.example), not double-clicked.
# Requires the Claude Code CLI installed and on PATH, signed in to your own
# account, with a read-only Gmail MCP connector already authorized.
set -u
cd "$(dirname "$0")"

# launchd/cron run with a minimal PATH that usually doesn't include Homebrew
# or npm global bin directories -- add the common locations defensively.
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin:$HOME/.npm-global/bin:$HOME/npm-global/bin"

TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p data/sync_logs
LOGFILE="data/sync_logs/gmail_sync_${TS}.log"

{
    echo "===== Gmail sync run started $(date) ====="
    # Bash is scoped to python commands only: this run reads untrusted email
    # content, and an unrestricted shell would let a prompt-injection attempt
    # in a crafted email execute arbitrary commands. The sync only ever needs
    # to run python against backend/repository.py, so that's all it gets.
    cat GMAIL_SYNC_TASK_PROMPT.md | claude -p --output-format text --allowedTools "Read Write Edit Glob Grep Bash(python:*) Bash(python3:*) mcp__claude_ai_Gmail__search_threads mcp__claude_ai_Gmail__get_thread mcp__claude_ai_Gmail__get_message mcp__claude_ai_Gmail__list_labels"
    echo "===== Gmail sync run finished $(date) ====="
} >> "$LOGFILE" 2>&1
