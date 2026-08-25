@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Identify THIS install's own server.py by its absolute path, not just
rem "backend\server.py" -- that fragment is identical across every copy of
rem JobTrace on the machine, so a relative-path match would (and once did)
rem mistake a different install's already-running server for this one.
set "SCRIPTPATH=%~dp0backend\server.py"

rem Avoid launching a second server if this install's own one is already running.
for /f "delims=" %%R in ('powershell -NoProfile -Command "$sp = $env:SCRIPTPATH; if (Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -like ('*' + $sp + '*') }) { 'RUNNING' } else { 'NOTRUNNING' }"') do set "SERVER_STATE=%%R"

if "%SERVER_STATE%"=="RUNNING" (
    start "" http://localhost:8766
    exit /b 0
)

set "PYEXE="

where python >nul 2>nul
if not errorlevel 1 (
    set "PYEXE=python"
    goto :found
)

rem Fallback: PATH may not have refreshed yet right after installing Python.
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" (
        set "PYEXE=%%D\python.exe"
        goto :found
    )
)

echo.
echo Python was not found on your PATH.
echo Please install Python 3.10 or later from https://www.python.org/downloads/
echo and make sure "Add python.exe to PATH" is checked during installation.
echo.
pause
exit /b 1

:found
rem pythonw.exe is the windowless twin of python.exe that ships alongside it -
rem this runs the server with no console window, ever.
if "%PYEXE%"=="python" (
    set "PYWEXE=pythonw.exe"
) else (
    set "PYWEXE=%PYEXE:python.exe=pythonw.exe%"
)

if not exist data mkdir data >nul 2>nul

start /B "" "%PYWEXE%" "%SCRIPTPATH%" > data\server.log 2>&1

ping 127.0.0.1 -n 3 >nul
start "" http://localhost:8766
exit /b 0
