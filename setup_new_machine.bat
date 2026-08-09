@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   A 股决策 Agent 系统 - 新机器一键环境准备.
echo   需要先装好：Git、Python 3.11+（详见 新机器部署指南.md）.
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 python，请先安装 Python 3.11 或 3.14：.
    echo        https://www.python.org/downloads/.
    echo        安装时务必勾选 Add python.exe to PATH，装完重开本窗口再运行.
    pause
    exit /b 1
)
echo [0/4] Python 版本： & python --version
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] 创建虚拟环境 .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请检查 Python 安装后重试.
        pause
        exit /b 1
    )
) else (
    echo [1/4] .venv 已存在，跳过.
)
echo.

echo [2/4] 安装依赖（首次约 5-10 分钟，请耐心等待）...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt -r streamlit\requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败（可能是网络问题），请重试或联系我.
    pause
    exit /b 1
)
echo.

if not exist ".env" (
    echo [3/4] 首次运行：从模板生成 .env ...
    copy ".env.example" ".env" >nul
    echo       接下来用记事本打开 .env 填写：.
    echo         - DEEPSEEK_API_KEY （必填）.
    echo         - SILICONFLOW_API_KEY （建议填，embedding 走云端免下载模型）.
    echo         - DRAGON_TIGER_ENABLE=true （需要游资追踪数据时）.
    start notepad ".env"
) else (
    echo [3/4] .env 已存在，跳过.
)
echo.

echo [4/4] 环境准备完成！.
echo.
echo ============================================================
echo  接下来两步启动（两个终端）：.
echo.
echo  终端1 - 后端：.
echo    cd /d "%~dp0backend".
echo    set PYTHONPATH=%~dp0;%~dp0backend.
echo    "..\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000.
echo.
echo  终端2 - 面板：.
echo    cd /d "%~dp0".
echo    ".venv\Scripts\python.exe" -m streamlit run streamlit\app.py --server.port 8501.
echo.
echo  然后浏览器打开 http://localhost:8501.
echo  详细说明与常见问题见 新机器部署指南.md.
echo ============================================================
pause
