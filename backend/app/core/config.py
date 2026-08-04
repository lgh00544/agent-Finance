"""
全局配置（pydantic-settings）
存储默认全栈本地文件（零外部依赖）：
  - 数据库：SQLite 单文件 data/dev.db（DB_BACKEND=mysql 可切外部 MySQL）
  - 缓存：进程内存（CACHE_BACKEND=redis 可切外部 Redis）
  - 向量库：本地文件模式 Qdrant data/qdrant_storage（QDRANT_MODE=server 可切外部服务）
所有密钥仅从环境变量/.env 读取，代码零硬编码。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]  # backend/
PROJECT_DIR = ROOT_DIR.parent                     # D:\self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 运行模式 ----------
    app_env: str = "dev"  # dev / prod（docker 部署标识，存储选择看下面三个后端开关）

    # ---------- 存储后端（默认全本地文件，切换只需改开关）----------
    db_backend: str = "sqlite"     # sqlite（默认，单文件 data/dev.db）/ mysql
    cache_backend: str = "memory"  # memory（默认，进程内）/ redis
    qdrant_mode: str = "local"     # local（默认，本地文件模式，存 data/qdrant_storage）/ server

    # ---------- MySQL（DB_BACKEND=mysql 时生效）----------
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_root_password: str = "change_me"
    mysql_database: str = "stock"

    # ---------- Redis（CACHE_BACKEND=redis 时生效）----------
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    # ---------- Qdrant 服务（QDRANT_MODE=server 时生效）----------
    qdrant_host: str = "127.0.0.1"
    qdrant_port: int = 6333

    # ---------- DeepSeek LLM ----------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_max_tokens: int = 8192  # 留足空间防大表输出 JSON 截断

    # ---------- Embedding ----------
    embedding_provider: str = "siliconflow"  # siliconflow / local
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_embedding_model: str = "BAAI/bge-m3"
    local_embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # ---------- 飞书告警 ----------
    feishu_webhook_url: str = ""

    # ---------- 资金与交易风格 ----------
    total_capital: float = 100000.0
    max_single_position_pct: float = 40.0
    trade_style: str = "波段趋势交易，中线持有，分批建仓，严格执行止损"

    # ---------- Discover 刚性过滤参数（客观条件，非主观判断）----------
    discover_top_n: int = 300   # 按成交额客观排序后送入 LLM 的股票数量
    min_amount: float = 1e8     # 最低成交额（元）：流动性刚性过滤

    # ---------- 调度 ----------
    discover_hour: int = 16
    discover_minute: int = 10
    monitor_interval_minutes: int = 5
    monitor_llm_cache_minutes: int = 15

    # ---------- OCR 持仓截图识别 ----------
    ocr_enable: bool = False  # true=启用 PaddleOCR 本地识别；false=关闭
    ocr_device: str = "cpu"   # cpu / gpu（gpu 需安装 paddlepaddle-gpu 与 CUDA）

    # ---------- 日志 ----------
    log_level: str = "INFO"

    # ---------- 数据源 ----------
    datasource_timeout: int = 15  # akshare 请求超时秒数

    # ---------- 派生路径 ----------
    @property
    def data_dir(self) -> Path:
        return PROJECT_DIR / "data"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def qdrant_path(self) -> Path:
        """本地文件模式 Qdrant 存储目录（迁移系统直接复制该目录）"""
        return self.data_dir / "qdrant_storage"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
