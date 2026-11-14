@echo off
rem Moni collector launcher.
rem Collects this PC's device information into moni-report.json.
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect.ps1"
echo.
echo Press any key to close.
pause >nul
