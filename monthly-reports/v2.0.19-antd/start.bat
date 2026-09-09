@echo off
cd /d "%~dp0"
if exist "测试能力成熟度月报.html" (
  start "" "测试能力成熟度月报.html"
  exit /b 0
)
if exist "dist\index.html" (
  start "" "dist\index.html"
  exit /b 0
)
echo Missing 测试能力成熟度月报.html
pause
exit /b 1
