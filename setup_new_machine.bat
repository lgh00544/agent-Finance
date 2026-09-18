@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo A 股决策 Agent 新机器一键初始化（多人版）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_new_machine.ps1" -Mode MultiUser -Start
if errorlevel 1 (
  echo.
  echo 初始化失败，请查看上面的错误信息。
  pause
  exit /b 1
)
start "" "http://127.0.0.1:5173"
