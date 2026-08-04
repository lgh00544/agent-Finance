"""本地开发启动脚本（dev 模式：SQLite + 内存缓存，无需 Docker）
用法: python backend/scripts/dev_run.py
启动后: API http://127.0.0.1:8000  面板 http://127.0.0.1:8501
"""
import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_BACKEND_DIR.parent))  # 项目根：agent_prompts/ 提示词包所在
os.environ.setdefault("APP_ENV", "dev")

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
