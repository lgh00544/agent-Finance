"""
FastAPI 入口：lifespan 启动日志/建表/APScheduler 调度
启动命令: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.logging import setup_logging
from app.db.session import init_db
from app.scheduler.jobs import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    start_scheduler()
    logger.info("系统启动完成")
    yield
    stop_scheduler()


app = FastAPI(title="Stock Agent Decision System", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 单用户本地面板，允许全部来源
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
