@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Codex-CLI equivalent of run_gmail_sync_claude.bat. Requires:
rem   1. The Codex CLI installed and on PATH, signed in to your own account.
rem   2. A read-only Gmail MCP connector registered in Codex's own config
rem      (~/.codex/config.toml, under [mcp_servers]) and authorized there —
rem      that's a one-time step you do yourself in Codex's own settings,
rem      this script can't set it up for you.
rem   3. An approval/sandbox mode configured (in ~/.codex/config.toml or via
rem      a flag on the line below) that lets this run unattended without
rem      pausing for interactive confirmation, scoped no wider than needed:
rem      write access to this project's data files, nothing else.
rem `codex exec` runs a prompt once, non-interactively, then exits. Flag
rem names have moved between Codex CLI versions — if this fails, run
rem `codex exec --help` and adjust the command below to match.

for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set TS=%%i
if not exist "data\sync_logs" mkdir "data\sync_logs"
set LOGFILE=data\sync_logs\gmail_sync_%TS%.log

set NPMPATH=%APPDATA%\npm
set PATH=%PATH%;%NPMPATH%

echo ===== Gmail sync run started %date% %time% ===== > "%LOGFILE%"

type GMAIL_SYNC_TASK_PROMPT.md | codex exec >> "%LOGFILE%" 2>&1

echo ===== Gmail sync run finished %date% %time% ===== >> "%LOGFILE%"

endlocal
