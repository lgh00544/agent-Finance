"""前端离线缓存：接口失败时降级展示最近一次成功数据（标注缓存时间，灰色弱化非最新）。

仅缓存轻量查询结果（如候选池列表）；写入失败静默忽略，绝不影响主流程与页面性能。
缓存文件落在 data/（已 gitignore），与服务端数据存储无关。
"""
import json
from datetime import datetime
from pathlib import Path

_CACHE_DIR = Path(__file__).resolve().parents[1] / "data"


def _path(key: str) -> Path:
    safe = "".join(c for c in key if c.isalnum() or c in "-_")
    return _CACHE_DIR / f"frontend_cache_{safe}.json"


def save(key: str, data) -> None:
    """保存最近一次成功数据（best-effort，失败静默）"""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "data": data}
        _path(key).write_text(json.dumps(payload, ensure_ascii=False),
                              encoding="utf-8")
    except OSError:
        pass


def load(key: str) -> dict | None:
    """读取最近一次成功缓存；无缓存或损坏返回 None"""
    try:
        return json.loads(_path(key).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
