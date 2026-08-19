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

from pydantic import Field, field_validator
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
    # 高频读接口结果缓存（秒）：候选/评分/建仓/持仓/告警/复盘列表短缓存，
    # 写操作自动失效保证一致；设为 0 关闭（数据变更需即时可见的场景可关）
    db_query_cache_ttl: int = 60

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

    # ---------- DeepSeek LLM（双模型分场景路由）----------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    # 轻量默认模型：高频轻量场景（Discover 初筛 / Monitor 盘中巡检 / 告警生成等），速度与成本优先
    deepseek_default_model: str = "deepseek-v4-flash"
    # 深度推理模型：复杂研判场景（市况评分 / 最终候选确认 / 五维打分 / 建仓方案 / 卖出决策 / 复盘与重思考）
    deepseek_reasoning_model: str = "deepseek-chat"
    # flash 输出上限：轻量场景足够，防止大 token 浪费（flash 不支持内部思考，无需预留思考预算）
    deepseek_flash_max_tokens: int = 8192
    llm_max_tokens: int = 32768  # 深度推理模型输出上限（留足空间防大表输出 JSON 截断，推理思考也计入输出）
    reasoning_effort: str = "low"  # 推理强度（仅深度推理模型生效，flash 不传推理参数）

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
    # 持仓参考风控比例（%）：持仓未手动设置止损/止盈且无关联建仓计划时，
    # 用于按持仓成本计算展示用参考价（仅展示，不落库、不触发任何判断）
    default_stop_loss_pct: float = 8.0
    default_take_profit_pct: float = 15.0

    # ---------- Discover 刚性过滤参数（客观条件，非主观判断）----------
    discover_top_n: int = 300   # 按成交额客观排序后送入 LLM 的股票数量
    min_amount: float = 1e8     # 最低成交额（元）：流动性刚性过滤

    # ---------- 市况评分 → 候选池上限档位（v2.0 前置步骤）----------
    # 每档 [最低分, 最高分, 候选池上限, 档位名]；.env 可用 JSON 覆盖 MARKET_CAP_BANDS
    market_cap_bands: list[list] = Field(
        default=[[0, 20, 5, "防御期"], [21, 35, 10, "过渡期"],
                 [36, 45, 15, "温和期"], [46, 50, 20, "强势期"]],
        description="市况评分（0-50）档位映射：分数区间 → 候选池上限 → 档位名")

    # ---------- 调度 ----------
    discover_hour: int = 16
    discover_minute: int = 10
    monitor_interval_minutes: int = 3  # 交易时段持仓监控间隔（分钟）
    monitor_llm_cache_minutes: int = 3  # 监控 LLM 结果缓存（与监控频率同节奏，保证信号时效）

    # ---------- OCR 持仓截图识别 ----------
    ocr_enable: bool = False  # true=启用 PaddleOCR 本地识别；false=关闭
    ocr_device: str = "cpu"   # cpu / gpu（gpu 需安装 paddlepaddle-gpu 与 CUDA）
    ocr_model_level: str = "light"  # light=轻量模型（默认，体积小）；full=完整模型（精度略高，体积更大）

    # ---------- MiniMax M3 可选多模态能力（默认关闭，零开销）----------
    # MiniMax M3 仅承担持仓截图 OCR 等视觉专项任务（预留 K 线图/财报截图等扩展场景），
    # 不参与五 Agent 选股/建仓/监控等核心业务研判（主模型仍为 DeepSeek）。
    # 默认关闭时系统行为与原版本完全一致：不加载任何依赖、不发起任何请求。
    minimax_enable: bool = False  # 多模态能力总开关（开启后 OCR 默认优先云端）
    minimax_api_key: str = ""     # MiniMax API 密钥（仅环境变量管理，禁止硬编码到业务代码）
    minimax_base_url: str = "https://api.minimax.chat/v1"  # 官方 OpenAI 兼容端点（国际站 api.minimaxi.com/v1）
    minimax_model: str = "MiniMax-M3"  # 模型 ID（官方文档 ID 含连字符）
    minimax_ocr_enable: bool = True    # true=默认优先 MiniMax 云端识别持仓截图，失败自动回退本地；false=强制仅用本地 PaddleOCR

    # ---------- 模型体系优化（2026-08-18，默认 fail-closed：全部关闭/原行为） ----------
    # 经验沉淀 Worker 识别提供方：minimax=用 MiniMax-M3（云端，不占本地算力，失败自动降级 deepseek flash）；
    # deepseek=原行为（llm_call_json LIGHT）。非法值回退 minimax。
    experience_worker_provider: str = "minimax"
    # Score 两段式粗筛：false=原行为（零回归）；true=LIGHT 粗筛后仅精打前 N 只（上线前必须先过回放误杀率 <5% 门槛）
    score_two_stage: bool = False
    score_two_stage_keep: int = 12  # 粗筛后保留上限（1≤keep≤20，非法值回退 12）
    # 模型成本单价（元/百万 tokens；默认 0=不计成本，按官网定价填写后生效）
    deepseek_cached_input_price: float = 0.0  # DeepSeek 缓存命中输入价
    deepseek_input_price: float = 0.0         # DeepSeek 未命中输入价
    deepseek_output_price: float = 0.0
    minimax_input_price: float = 0.0
    minimax_output_price: float = 0.0

    @field_validator("experience_worker_provider")
    @classmethod
    def _validate_worker_provider(cls, v: str) -> str:
        return v if v in ("minimax", "deepseek") else "minimax"

    @field_validator("score_two_stage_keep")
    @classmethod
    def _clamp_keep(cls, v: int) -> int:
        return 12 if not (1 <= v <= 20) else v

    # ---------- 日志（自动轮转，防无限增长）----------
    log_level: str = "INFO"
    log_max_bytes_mb: int = 10   # 单个日志文件上限（MB）
    log_backup_count: int = 5    # 轮转保留份数（单文件×份数≈日志总占用上限）

    # ---------- 数据源 ----------
    datasource_timeout: int = 5  # akshare 请求超时秒数（15→5：降级时快速失败，防 300 股串行拖死）

    # ---------- 数据源稳定性（请求加固/断路器/限流） ----------
    # 东财/新浪实时接口易被反爬限流：浏览器请求头 + 超时拆分 + 失败后间隔重试 1 次 +
    # 连续失败进入临时降级（只走备用源，冷却到期静默探测自动切回），避免次次打主源刷日志。
    datasource_connect_timeout: float = 5    # 连接超时秒数（TCP 握手）
    datasource_read_timeout: float = 15      # 读取超时秒数
    datasource_retry_times: int = 1          # 实时热点路径失败后重试次数（间隔 1-2s，勿立即重试触发限流）
    datasource_retry_delay: float = 1.5      # 重试间隔秒数
    datasource_breaker_threshold: int = 3    # 连续失败次数阈值，达到后进入临时降级
    datasource_breaker_cooldown: int = 600   # 临时降级持续时间（秒），到期下次调用静默探测主源
    datasource_min_request_interval: float = 0.5  # 同类实时请求最小间隔（秒），高频场景自动补齐间隔
    datasource_user_agent: str = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                  "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")

    # ---------- 麦蕊智数增强数据源（可选，默认关闭）----------
    # 麦蕊（mairui.club）作为 akshare 的补充数据源：仅用于 v2.0 选股机制的高级资金面/股东面字段，
    # 基础行情数据仍优先走 akshare（东财→新浪双通道），减少配额消耗。默认关闭时行为与之前完全一致。
    mairui_enable: bool = False
    mairui_licence: str = ""  # 证书密钥（仅从环境变量 MAIRUI_LICENCE 读取，禁止硬编码入库）
    mairui_base_url: str = "https://api.mairuiapi.com"

    # ---------- 龙虎榜数据源（游资维度，可选；T+1 16:30 后拉前一日） ----------
    # 龙虎榜流水落 lhb_original_flow 表，多源校验在 services/hot_money.py：
    # 同一(日期,标的,口径)至少 2 源且差值 < verify_threshold% 才采信，否则标"数据置信度不足"仅参考。
    dragon_tiger_enable: bool = False      # 总开关 DRAGON_TIGER_ENABLE（关闭时抓取方法返回空）
    dragon_tiger_hour: int = 16            # T+1 定时拉取小时
    dragon_tiger_minute: int = 30          # T+1 定时拉取分钟
    dragon_tiger_verify_threshold: float = 10.0  # 多源校验差值阈值（%），超过则标置信度不足
    # 第二龙虎榜数据源开关 DRAGON_TIGER_SECOND_SOURCE：
    #   auto = 自动探测可用第二源（当前：同花顺直连需 JS hexin-v token 不可用、
    #          新浪每日明细无金额明细 → 仅东财可用，诚实标注"采信待第二源"，不伪造第二源数据 K227）；
    #   sina = 新浪（仅上榜确认，无金额，不参与金额采信）；
    #   none = 明确只用东财单源（置信度不足降级保留）。
    dragon_tiger_second_source: str = "auto"

    # ---------- 存储空间维护（低频自动清理，防无限堆积）----------
    news_retention_days: int = 90        # 新闻/公告保留周期（天），超期自动清理（关键分析数据不清理）
    db_maintenance_enabled: bool = True  # 定时空间维护总开关（SQLite VACUUM + 超期数据清理）
    db_maintenance_day_of_week: int = 6  # 每周执行日（0=周一 … 6=周日），默认周日凌晨
    db_maintenance_hour: int = 5
    db_maintenance_minute: int = 30

    # ---------- 向量库 ----------
    qdrant_compression: bool = True  # 本地文件模式默认启用标量量化压缩，减少向量库磁盘占用

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


def market_band_info(score: float) -> tuple[int, str]:
    """市况评分 → (当日候选池上限, 档位名)。档位为人工设定映射，非市场判断。"""
    for low, high, cap, name in settings.market_cap_bands:
        if low <= score <= high:
            return int(cap), str(name)
    last = settings.market_cap_bands[-1]
    return int(last[2]), str(last[3])
