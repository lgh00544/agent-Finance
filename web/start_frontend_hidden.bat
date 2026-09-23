@echo off
REM 前端启动脚本（由 PowerShell 启动器隐藏调用）
cd /d "%~dp0"
if not "%~1"=="" (set "VITE_API_PROXY=%~1") else (set "VITE_API_PROXY=http://127.0.0.1:8100")
set CODEBUDDY_SAFE_DELETE_ENABLED=0
set CODEBUDDY_SAFE_DELETE_SANDBOX=0
call pnpm.cmd dev --host 0.0.0.0 --port 5173 --strictPort
