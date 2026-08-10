"""pytest 全局配置：dev 模式（SQLite，测试库与 dev.db 隔离）+ 项目路径"""
import os
import sys
import tempfile

os.environ.setdefault("APP_ENV", "dev")
# 强制测试走本地 SQLite（环境变量优先于 .env）：主库已切 TiDB（.env DB_BACKEND=mysql），
# 若不覆盖，测试会连云端生产库并互相污染/误写真实数据（2026-08-10 曾致 market_condition 污染）
os.environ.setdefault("DB_BACKEND", "sqlite")
# 测试库落在系统临时目录，按进程 PID 隔离，不污染 data/dev.db
os.environ.setdefault(
    "SQLITE_PATH",
    os.path.join(tempfile.gettempdir(), f"stock_test_{os.getpid()}.db"),
)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)
# 项目根目录（agent_prompts/ 提示词包所在）
sys.path.insert(0, os.path.dirname(_BACKEND_DIR))
