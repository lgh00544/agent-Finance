"""pytest 全局配置：dev 模式（SQLite，测试库与 dev.db 隔离）+ 项目路径"""
import os
import sys
import tempfile

os.environ.setdefault("APP_ENV", "dev")
# 测试库落在系统临时目录，按进程 PID 隔离，不污染 data/dev.db
os.environ.setdefault(
    "SQLITE_PATH",
    os.path.join(tempfile.gettempdir(), f"stock_test_{os.getpid()}.db"),
)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)
# 项目根目录（agent_prompts/ 提示词包所在）
sys.path.insert(0, os.path.dirname(_BACKEND_DIR))
