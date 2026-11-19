@echo off
setlocal
rem Moni collector launcher.
rem Collects this PC's device information into moni-report.json.
cd /d "%~dp0" || exit /b 1
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect.ps1"
set "collectorExit=%ERRORLEVEL%"
echo.
echo Press any key to close.
pause >nul
exit /b %collectorExit%
