@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set TS=%%i
if not exist "data\sync_logs" mkdir "data\sync_logs"
set LOGFILE=data\sync_logs\gmail_sync_%TS%.log

set NPMPATH=%APPDATA%\npm
set PATH=%PATH%;%NPMPATH%

echo ===== Gmail sync run started %date% %time% ===== > "%LOGFILE%"

rem Bash is scoped to python commands only: this run reads untrusted email
rem content, and an unrestricted shell would let a prompt-injection attempt
rem in a crafted email execute arbitrary commands. The sync only ever needs
rem to run python against backend/repository.py, so that's all it gets.
type GMAIL_SYNC_TASK_PROMPT.md | claude -p --output-format text --allowedTools "Read Write Edit Glob Grep Bash(python:*) Bash(python3:*) mcp__claude_ai_Gmail__search_threads mcp__claude_ai_Gmail__get_thread mcp__claude_ai_Gmail__get_message mcp__claude_ai_Gmail__list_labels" >> "%LOGFILE%" 2>&1

echo ===== Gmail sync run finished %date% %time% ===== >> "%LOGFILE%"

endlocal
