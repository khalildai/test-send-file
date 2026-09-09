@echo off
cd /d "%~dp0"
echo Starting monthly report (antd)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Startup failed.
  pause
)
exit /b %EXIT_CODE%
