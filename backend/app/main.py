"""
FastAPI 入口：lifespan 启动日志/建表/APScheduler 调度
启动命令: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.logging import setup_logging
from app.db import repo
from app.db.session import init_db
from app.scheduler.jobs import start_scheduler, stop_scheduler
from app.services import market_view, reasoning_trace

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    repo.seed_default_hot_money_profiles()  # 游资档案种子（幂等，席位名仅作模糊匹配参考）
    start_scheduler()

    # 首屏预热：三大指数后台异步拉取（akshare 冷启动约 36s，后台跑不阻塞启动；
    # 失败静默降级，60s 缓存命中后首屏秒回）
    def _warm_index_quotes() -> None:
        try:
            market_view.index_quotes()
        except Exception:  # noqa: BLE001 预热失败不阻塞启动
            logger.debug("指数行情预热失败（忽略）", exc_info=True)
    threading.Thread(target=_warm_index_quotes, name="warm-index-quotes", daemon=True).start()

    logger.info("系统启动完成")
    yield
    stop_scheduler()
    reasoning_trace.flush()  # 退出前兜底写入未落库的留痕记录


app = FastAPI(title="Stock Agent Decision System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 单用户本地面板，允许全部来源
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# ================= React SPA 静态挂载（web/dist 存在时同源单入口；不存在优雅降级仅 API 模式） =================
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"

if WEB_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="web-assets")

    @app.get("/", include_in_schema=False)
    async def web_index():
        return FileResponse(WEB_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def web_spa(full_path: str):
        # API 前缀兜底：未匹配到的 /api/* 明确 404，不落入 index.html
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API 路径不存在")
        f = WEB_DIST / full_path
        if f.is_file():
            return FileResponse(f)
        # SPA 路由：所有非文件路径回退 index.html（前端路由接管）
        return FileResponse(WEB_DIST / "index.html")
