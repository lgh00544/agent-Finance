"""本地开发启动脚本（dev 模式：SQLite + 内存缓存，无需 Docker）
用法: python backend/scripts/dev_run.py
启动后: API http://127.0.0.1:8000  面板 http://127.0.0.1:8501

启动钩子：SYNC_ON_START=true（.env 默认）时，uvicorn 起服务前先执行
sync_manager.py backup（云端 TiDB 全量 → 本地 SQLite data/dev.db，含自动快照备份）。
同步任何失败只降级不阻塞：提示后照常使用本地旧快照启动。
"""
import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_BACKEND_DIR.parent))  # 项目根：agent_prompts/ 提示词包 + sync_manager.py 所在
os.environ.setdefault("APP_ENV", "dev")

from app.core.logging import get_logger  # noqa: E402

log = get_logger("dev_run")


def _env_flag(name: str, default: bool = True) -> bool:
    """读布尔开关。os.environ 优先（可在命令行覆盖，如 SYNC_ON_START=false python ...）；
    pydantic-settings 不把 .env 注入 os.environ，脚本层兜底直接解析项目根 .env。
    显式 false 值（0/false/no/off）才视为关，其余视为开。"""
    raw = os.environ.get(name)
    if raw is None:
        env_file = _BACKEND_DIR.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(name + "="):
                    raw = line.split("=", 1)[1].strip()
                    break
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _sync_on_start() -> None:
    """SYNC_ON_START=true 时先同步云端 TiDB → 本地 SQLite 再起服务。

    import 复用 sync_manager.cmd_backup()（不另起子进程）；其自会把 backend 加入
    sys.path，与上方已插入的路径一致，无冲突。同步过程全兜底：任何异常打警告后
    照常启动（本地有旧快照可读），绝不因同步失败中断 backend 启动。
    """
    if not _env_flag("SYNC_ON_START", default=True):
        log.info("SYNC_ON_START=false：跳过启动同步")
        return
    try:
        # 惰性 import：开关关闭时零额外依赖加载
        import sync_manager  # noqa: F401
        from app.core.config import settings

        if settings.db_backend != "mysql":
            log.info("DB_BACKEND=%s：未配置云端，跳过启动同步", settings.db_backend)
            return
        log.info("SYNC_ON_START=true：同步云端 TiDB → 本地 SQLite（sync_manager backup）...")
        rc = sync_manager.cmd_backup()
        if rc == 0:
            log.info("启动同步完成：本地 data/dev.db 已与云端对齐")
        else:
            log.warning("启动同步存在失败表（rc=%s），继续用本地数据启动", rc)
    except Exception as exc:  # noqa: BLE001 同步失败降级：提示但继续启动本地数据
        log.warning("启动同步失败（%s），降级使用本地数据启动", exc)


if __name__ == "__main__":
    _sync_on_start()

    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
