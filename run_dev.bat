@echo off
rem ============================================================
rem  旧版单用户入口已停用。正式版本为多人认证版。
rem  请运行 start_multi_user.ps1（或 setup_new_machine.bat）。
rem  保留此文件仅用于避免旧快捷方式失效时误启动单用户同步流程。
rem ============================================================
echo [已停用] run_dev.bat 是旧版单用户启动入口。
echo 请改用：powershell -ExecutionPolicy Bypass -File "%~dp0start_multi_user.ps1"
exit /b 2

rem 以下旧实现故意保留在文件中，便于历史回退，不会被执行。
rem setlocal
rem cd /d "%~dp0"

set PY=%~dp0.venv\Scripts\python.exe
rem set ST=D:\space\self\self\.venv\Scripts\streamlit.exe   (Streamlit 已退役，不再启动)

if not exist "%PY%" (
    echo [ERROR] venv python not found: %PY%
    pause
    exit /b 1
)

rem ---- 读取 .env 的 SYNC_ON_START（默认 true；显式 false 才跳过同步）----
set SYNC_ON_START=true
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (`findstr /b "SYNC_ON_START=" .env`) do set "SYNC_ON_START=%%b"
)

if /I "%SYNC_ON_START%"=="false" (
    echo ============================================================
    echo  [1/3] SYNC_ON_START=false：跳过云端同步，直接启动本地数据
    echo ============================================================
    goto skip_sync
)

echo ============================================================
echo  [1/3] 同步云端到本地 (sync_manager.py backup)
echo ============================================================
"%PY%" sync_manager.py backup
if errorlevel 1 (
    echo [WARN] sync has issue, continue with current local data.
) else (
    echo [OK] sync done.
)
rem 同步已在 bat 完成，置 false 避免 dev_run.py 重复再拉一次云端
set SYNC_ON_START=false

:skip_sync

echo.
echo ============================================================
echo  [2/3] 启动 Backend  (http://127.0.0.1:8000)
echo ============================================================
start "stock-backend" cmd /c ""%PY%" backend\scripts\dev_run.py"

echo.
echo ============================================================
echo  [3/3] 启动 React 前端 (http://localhost:5173)
echo ============================================================
rem ---- Streamlit（8501）已退役，以下旧入口不再执行 ----
rem start "stock-streamlit" cmd /c ""%ST%" run streamlit\app.py"
start "stock-web" cmd /c "cd /d "%~dp0web" && npm run dev"

echo.
echo React 前端已退出，如需停止 backend 请关闭 "stock-backend" 窗口。
pause
endlocal
