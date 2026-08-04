# ============================================================
# 后端镜像：Python 3.11 + FastAPI + APScheduler
# ============================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 系统依赖：akshare 需要部分编译/网络相关包；libgl1 供 OCR 的 opencv 读图使用
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tzdata libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY agent_prompts ./agent_prompts

EXPOSE 8000

# 启动 FastAPI + 内置 APScheduler（lifespan 中启动）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
