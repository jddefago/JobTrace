#!/bin/bash
# macOS/Linux equivalent of run_gmail_sync_codex.bat. Requires:
#   1. The Codex CLI installed and on PATH, signed in to your own account.
#   2. A read-only Gmail MCP connector registered in Codex's own config
#      (~/.codex/config.toml, under [mcp_servers]) and authorized there --
#      that's a one-time step you do yourself in Codex's own settings,
#      this script can't set it up for you.
#   3. An approval/sandbox mode configured (in ~/.codex/config.toml or via
#      a flag on the line below) that lets this run unattended without
#      pausing for interactive confirmation, scoped no wider than needed:
#      write access to this project's data files, nothing else.
# `codex exec` runs a prompt once, non-interactively, then exits. Flag names
# have moved between Codex CLI versions -- if this fails, run
# `codex exec --help` and adjust the command below to match.
set -u
cd "$(dirname "$0")"

export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin:$HOME/.npm-global/bin:$HOME/npm-global/bin"

TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p data/sync_logs
LOGFILE="data/sync_logs/gmail_sync_${TS}.log"

{
    echo "===== Gmail sync run started $(date) ====="
    cat GMAIL_SYNC_TASK_PROMPT.md | codex exec
    echo "===== Gmail sync run finished $(date) ====="
} >> "$LOGFILE" 2>&1
