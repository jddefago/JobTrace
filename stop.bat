@echo off
setlocal
cd /d "%~dp0"

rem Match THIS install's own server.py by absolute path -- see start.bat's
rem comment. A relative-path match would risk stopping a different
rem JobTrace install's server instead of (or as well as) this one.
set "SCRIPTPATH=%~dp0backend\server.py"

echo Stopping JobTrace...
powershell -NoProfile -Command "$sp = $env:SCRIPTPATH; $procs = Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -like ('*' + $sp + '*') }; if ($procs) { $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Write-Output 'JobTrace server stopped.' } else { Write-Output 'JobTrace was not running.' }"

pause
