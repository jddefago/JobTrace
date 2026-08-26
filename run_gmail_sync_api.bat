@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Scheduled-task runner for the headless Gmail sync (backend/gmail_api_sync.py).
rem Unlike run_gmail_sync_claude.bat/run_gmail_sync_codex.bat, this needs no
rem AI assistant app installed -- only Python and the dependencies in
rem requirements.txt, plus the one-time setup in GMAIL_SYNC_API.md (Google
rem OAuth client + Anthropic API key). Run once manually first so the Gmail
rem OAuth consent screen can be completed interactively; after that the
rem cached token lets this run fully unattended.

for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"`) do set TS=%%i
if not exist "data\sync_logs" mkdir "data\sync_logs"
set LOGFILE=data\sync_logs\gmail_sync_api_task_%TS%.log

echo ===== Gmail API sync run started %date% %time% ===== > "%LOGFILE%"
python backend\gmail_api_sync.py >> "%LOGFILE%" 2>&1
echo ===== Gmail API sync run finished %date% %time% ===== >> "%LOGFILE%"

endlocal
