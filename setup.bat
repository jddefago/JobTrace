@echo off
rem One-time setup for a fresh JobTrace download on Windows. Safe to re-run.
rem Double-click this file, or run it from a terminal.
setlocal enabledelayedexpansion
cd /d "%~dp0"
set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"

echo JobTrace setup
echo ==============
echo.

rem 1. Python check.
set "PYEXE="
where python >nul 2>nul && set "PYEXE=python"
if not defined PYEXE (
    for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" set "PYEXE=%%D\python.exe"
    )
)
if not defined PYEXE (
    echo   Python 3 was not found.
    echo   Install it from https://www.python.org/downloads/ ^(tick "Add python.exe
    echo   to PATH" during setup^) and run this again.
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%V in ('"%PYEXE%" --version 2^>^&1') do echo   Python: %%V

rem 2. (Re)create the Desktop shortcut with this folder's path baked in.
set "LNK=%UserProfile%\Desktop\JobTrace.lnk"
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');" ^
  "$s.TargetPath='%PROJ%\start_hidden.vbs';" ^
  "$s.WorkingDirectory='%PROJ%';" ^
  "if (Test-Path '%PROJ%\assets\logo.ico') { $s.IconLocation='%PROJ%\assets\logo.ico,0' };" ^
  "$s.Save()"
echo   Created Desktop shortcut "JobTrace"

rem 3. Start the server and open the dashboard.
echo.
call start.bat

echo.
echo   JobTrace is running at http://localhost:8766
echo.
echo   Gmail sync is OPTIONAL and off by default. The tracker works fully
echo   without it. To turn it on later, open the dashboard, click the Gmail
echo   pill (top-right) and choose "Sync settings" - or ask your AI assistant
echo   to "set up JobTrace Gmail sync" and point it at SETUP.md.
echo.
pause
