@echo off
setlocal
cd /d "%~dp0"
echo Starting V2.0.12d2... Please wait.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Startup failed. See startup.log in this folder.
  pause
)
exit /b %EXIT_CODE%
