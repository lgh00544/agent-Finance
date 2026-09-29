@echo off
rem ============================================================
rem  A股后端开机自动启动脚本(由 Windows 任务计划程序在登录时调用)
rem  启动 FastAPI 后端 http://127.0.0.1:8000(看板/DSH工具依赖此服务)
rem ============================================================
cd /d "D:\space\self\self"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] venv python not found: D:\space\self\self\.venv\Scripts\python.exe
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "backend\scripts\dev_run.py"
