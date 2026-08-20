# akshare 数据源稳定性根治（C 方案：4 张表 + 4 个 cron + 三源降级链 + 监控面板）

## 一、背景

sir 反馈 2026-08-20 13:24 持仓监控页报"中仓仓位服务失败 / 网络错误：无法连接到服务器"，截图报错框持续 5+ 分钟，期间后端 curl `/api/holdings` 实测 5 连击 HTTP 200 / P95 290ms 健康，**前端 15s 超时**是体感根因，但**深层根因是数据源 akshare 偶发慢+无降级**——

**当前不稳定数据源全景**（基于 8/19 板块优化后的剩余未覆盖项）：
1. ❌ 个股实时报价 `GET /api/holdings/quotes`——直连 akshare，无缓存
2. ❌ 龙虎榜 / 大宗交易 / 北向资金（游资追踪）——单源 akshare，断路器未加
3. ⚠️ LLM 推理（DeepSeek）——长尾 timeout 仍存在
4. ✅ 板块快照——8/19 已根治（sector_snapshot 表 + cron */5 + 断路器）

**目标**：把"断路器 + DB 落库 + cron 定时刷新 + 三源降级链"这套已验证模式（来自 sector_snapshot）**横向推广到全部 akshare 读路径**，前端不再看到"网络错误"，后端失败率从 ~14% 压到 < 1%。

## 二、改动清单

### 后端（4 个新表 + 4 个新服务 + 4 个新 cron + 1 个共享降级链工具 + 1 个监控接口）

| # | 文件 | 类型 | 作用 |
|---|---|---|---|
| 1 | `backend/app/datasource/sources.py` | 新建 | 共享三源降级链工具 `safe_fetch(akshare_func, fallback_chain, breaker)` |
| 2 | `backend/app/services/quote_snapshot.py` | 新建 | 个股实时报价快照（akshare → 新浪 → 东财 HTTP 三源） |
| 3 | `backend/app/services/hotmoney_snapshot.py` | 新建 | 龙虎榜 / 大宗交易 / 北向资金快照（akshare → 第二源） |
| 4 | `backend/app/services/market_index_snapshot.py` | 新建 | 大盘指数实时快照（上证/深证/创业板/科创50，akshare → 新浪） |
| 5 | `backend/app/services/llm_cache.py` | 新建 | LLM 推理结果缓存（key=prompt_hash, TTL=24h，避免重复推理） |
| 6 | `backend/app/api/routes.py` | 改 | 新增 5 个查询端点（读快照表，不直连 akshare） |
| 7 | `backend/app/scheduler/jobs.py` | 改 | 新增 4 个 cron 入口 + 1 个监控状态端点 |
| 8 | `backend/app/db/models.py` | 改 | 新增 5 张表 ORM（quote_snapshot / hotmoney_snapshot / market_index_snapshot / llm_cache / datasource_health） |
| 9 | `backend/app/db/repo.py` | 改 | 新增 8 个 repo 函数（upsert + list + get_latest + health） |
| 10 | `init.sql` | 改 | 新增 5 张表 DDL（AUTO_INCREMENT + String(10) + 索引） |
| 11 | `backend/app/datasource/akshare_source.py` | 改 | 标记为"主源"，所有 fetch_xxx 方法加入"是否走三源降级"开关 |
| 12 | `backend/app/datasource/market_hours.py` | 改 | 断路器现有逻辑抽出，改为通用 `CircuitBreaker` 类 |
| 13 | `backend/app/services/dashboard.py` | 改 | 数据源健康度卡片（"akshare 今日成功率 99.2% / 失败 3 次 / 当前状态 正常"） |
| 14 | `backend/tests/test_source_stability.py` | 新建 | 8 个测试（断路器/降级/缓存/兜底） |

### 前端（仅改 4 个页面，添加降级状态提示）

> 🔴 按 2026-08-20 sir 拍板"前端默认改新版 React"——**只改 `web/src/`，不动 `streamlit/`**

| # | 文件 | 改动 |
|---|---|---|
| 15 | `web/src/api/client.ts` | 改：`toErr` 文案分超时/网络断/服务端错 3 类；增加 `getWithRetry` 退避重试 |
| 16 | `web/src/pages/HoldingsPage.tsx` | 改：报价列改读 `/api/holdings/quotes-snapshot`（新表），加 stale 角标 |
| 17 | `web/src/pages/HotMoneyPage.tsx` | 改：游资维度数据改读 `/api/hotmoney/snapshot`（新表） |
| 18 | `web/src/pages/OverviewPage.tsx` | 改：大盘指数卡片改读 `/api/market/index-snapshot`；新增数据源健康度卡片 |
| 19 | `web/src/components/common/StaleBadge.tsx` | 新建：通用 stale 角标组件（"数据 X 分钟前"） |
| 20 | `web/src/components/common/SourceHealth.tsx` | 新建：数据源健康度徽章（绿/黄/红三态） |

## 三、数据库设计

### 表 1：quote_snapshot（个股实时报价快照）

```sql
CREATE TABLE quote_snapshot (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    stock_code      VARCHAR(10) NOT NULL COMMENT '股票代码 600519.SH',
    current_price   DECIMAL(10,3) COMMENT '当前价',
    change_pct      DECIMAL(8,3) COMMENT '涨跌幅%',
    volume          BIGINT COMMENT '成交量(股)',
    turnover        DECIMAL(18,2) COMMENT '成交额(元)',
    source          VARCHAR(16) NOT NULL COMMENT '数据源 em/sina/tencent',
    refreshed_at     DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stock_time (stock_code, refreshed_at),
    KEY idx_refreshed (refreshed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个股实时报价快照（每 2 分钟刷新）';
```

### 表 2：hotmoney_snapshot（龙虎榜/大宗交易/北向资金快照）

```sql
CREATE TABLE hotmoney_snapshot (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    snapshot_type   VARCHAR(20) NOT NULL COMMENT 'lhb/block/north',
    trade_date      VARCHAR(10) NOT NULL COMMENT 'YYYY-MM-DD',
    payload         JSON NOT NULL COMMENT '原始数据 JSON',
    source          VARCHAR(16) NOT NULL COMMENT 'em/sina',
    refreshed_at    DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_type_date (snapshot_type, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游资维度数据快照';
```

### 表 3：market_index_snapshot（大盘指数快照）

```sql
CREATE TABLE market_index_snapshot (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    index_code      VARCHAR(16) NOT NULL COMMENT '000001.SH / 399001.SZ / 399006.SZ / 000688.SH',
    index_name      VARCHAR(32) NOT NULL,
    current_value   DECIMAL(12,3),
    change_pct      DECIMAL(8,3),
    source          VARCHAR(16) NOT NULL,
    refreshed_at    DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_idx_time (index_code, refreshed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大盘指数快照';
```

### 表 4：llm_cache（LLM 推理结果缓存）

```sql
CREATE TABLE llm_cache (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    prompt_hash     VARCHAR(64) NOT NULL COMMENT 'SHA256(prompt + model + temperature)',
    response        TEXT NOT NULL,
    model           VARCHAR(32) NOT NULL,
    input_tokens    INT,
    output_tokens   INT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      DATETIME NOT NULL,
    KEY idx_hash_expires (prompt_hash, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM 推理结果缓存（24h TTL）';
```

### 表 5：datasource_health（数据源健康度监控）

```sql
CREATE TABLE datasource_health (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    source_name     VARCHAR(32) NOT NULL COMMENT 'akshare_main/sina_fallback/...',
    success_count   INT NOT NULL DEFAULT 0,
    fail_count      INT NOT NULL DEFAULT 0,
    last_success_at DATETIME,
    last_fail_at    DATETIME,
    last_error      TEXT,
    circuit_state   VARCHAR(16) NOT NULL DEFAULT 'closed' COMMENT 'closed/open/half_open',
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_source (source_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据源健康度（实时统计）';
```

## 四、共享降级链工具 `backend/app/datasource/sources.py`

```python
"""三源降级链工具：所有 akshare 调用统一通过此入口
- 断路器（连续失败 N 次自动短路 N 秒）
- 指数退避重试（1s/2s/4s）
- 多源降级（主源 → 降级1 → 降级2）
- 健康度上报（写 datasource_health 表）
"""
from typing import Callable, Sequence
from functools import wraps
import time
import hashlib
import logging
from app.db import repo

logger = logging.getLogger(__name__)

BREAKER_FAIL_THRESHOLD = 3       # 连续失败 3 次开断路器
BREAKER_OPEN_SECONDS = 60        # 短路 60 秒
RETRY_BACKOFF = [1, 2, 4]        # 退避秒数


def _circuit_state(source: str) -> str:
    """读断路器状态（closed/open/half_open）"""
    row = repo.get_datasource_health(source)
    if not row:
        return "closed"
    if row["circuit_state"] == "open":
        if row["updated_at"] and (time.time() - row["updated_at"].timestamp()) > BREAKER_OPEN_SECONDS:
            return "half_open"
    return row["circuit_state"]


def _report(source: str, success: bool, error: str | None = None) -> None:
    """上报调用结果到 datasource_health"""
    repo.upsert_datasource_health(source, success=success, error=error)


def _try_call(func: Callable, source: str) -> object:
    """单源调用 + 指数退避重试"""
    last_err = None
    for attempt, delay in enumerate([0] + RETRY_BACKOFF):
        if delay:
            time.sleep(delay)
        try:
            result = func()
            if attempt > 0:
                logger.info("[%s] 第 %d 次重试成功", source, attempt)
            return result
        except Exception as exc:
            last_err = exc
            logger.warning("[%s] 第 %d 次失败: %s", source, attempt + 1, exc)
    raise last_err


def safe_fetch(source_chain: Sequence[tuple[str, Callable]]) -> object:
    """三源降级链：依次尝试每个 (source_name, fetch_func)，断路器开的源跳过

    用法：
        safe_fetch([
            ("akshare_main", lambda: akshare.fetch_xxx()),
            ("sina_fallback", lambda: sina.fetch_xxx()),
            ("tencent_fallback", lambda: tencent.fetch_xxx()),
        ])
    """
    for source, func in source_chain:
        state = _circuit_state(source)
        if state == "open":
            logger.info("[%s] 断路器开启，跳过", source)
            continue
        try:
            result = _try_call(func, source)
            _report(source, success=True)
            return {"data": result, "source": source, "stale": False}
        except Exception as exc:
            _report(source, success=False, error=str(exc)[:200])
            continue
    raise RuntimeError(f"全部 {len(source_chain)} 个数据源均失败")


def cached_llm_call(prompt: str, model: str, temperature: float, llm_func: Callable) -> str:
    """LLM 推理缓存包装：相同 prompt 24h 内不重复推理"""
    key = hashlib.sha256(f"{model}|{temperature}|{prompt}".encode()).hexdigest()
    cached = repo.get_llm_cache(key)
    if cached and cached["expires_at"] > time.time():
        return cached["response"]
    response = llm_func()
    repo.upsert_llm_cache(key, response, model, ttl=86400)
    return response
```

## 五、Cron 配置

在 `backend/app/scheduler/jobs.py` 的 `start_scheduler()` 末尾追加（紧跟 sector_refresh_job 之后）：

```python
# 个股报价快照：每 2 分钟（盘中 9:00-15:55 有效；函数内过滤交易时段）
scheduler.add_job(quote_refresh_job, "cron",
                  day_of_week="mon-fri", hour="9-15", minute="*/2",
                  id="quote_refresh", name="个股报价快照刷新",
                  replace_existing=True, misfire_grace_time=120)

# 龙虎榜 T+1 16:30 + 兜底 18:00（已有 dragon_tiger_job，加个 staleness 检测分支）
# 不重复加 cron，复用现有 dragon_tiger_job，在函数内判定 snapshot 是否 stale 触发拉取

# 大盘指数快照：每 1 分钟（最关键，OverviewPage 首页用）
scheduler.add_job(market_index_refresh_job, "cron",
                  day_of_week="mon-fri", hour="9-15", minute="*/1",
                  id="market_index_refresh", name="大盘指数快照刷新",
                  replace_existing=True, misfire_grace_time=60)

# 数据源健康度统计：每 5 分钟汇总
scheduler.add_job(datasource_health_job, "cron", minute="*/5",
                  id="datasource_health", name="数据源健康度汇总",
                  replace_existing=True, misfire_grace_time=300)
```

## 六、关键查询端点

```python
# backend/app/api/routes.py 新增

@router.get("/holdings/quotes-snapshot")
def get_holdings_quotes_snapshot():
    """持仓个股实时报价（读 quote_snapshot 表，100% 可用）"""
    ...

@router.get("/hotmoney/snapshot")
def get_hotmoney_snapshot(type: str = "lhb"):
    """游资维度数据快照"""
    ...

@router.get("/market/index-snapshot")
def get_market_index_snapshot():
    """大盘指数快照"""
    ...

@router.get("/system/datasource-health")
def get_datasource_health():
    """数据源健康度（前端 OverviewPage 监控卡片用）"""
    ...
```

## 七、红线约束

1. **后端永不直接调 akshare**——所有读 akshare 的接口必须通过 `safe_fetch(...)` 走降级链
2. **三源降级链必须有 ≥ 2 个源**——单源场景直接报错，不假装有降级
3. **断路器开启 60s 后自动 half_open**——half_open 状态允许一次试调用，成功则 closed，失败则 open
4. **cron 频率不能超过数据源刷新速度**——akshare 实时报价限频 1 次/秒，cron */1 = 60s/次 安全
5. **新增表 DDL 必须用 MySQL 语法**（AUTO_INCREMENT + ENGINE=InnoDB + utf8mb4），不能混用 SQLite 语法
6. **字段长度统一 String(10)**（项目规范，trade_date 格式 YYYY-MM-DD）
7. **改后端接口时旧端点不能删**——保留向后兼容，灰度迁移
8. **LLM 缓存不存敏感信息**——prompt 可能含用户标的，但需 24h TTL 防止长期留存
9. **数据源失败率写日志**——每次 _report 都打 warning，前端监控面板读 datasource_health 表

## 八、回滚方案

- 新增 5 张表都是**只新增**，无任何原表 DDL 变更
- 新增 4 个 cron 独立 ID，删除 cron 即可停止
- 新增 5 个端点 path 唯一，删除 route 即可
- 新增 1 个 `safe_fetch` 工具，原有 akshare 直连路径不变（向后兼容）
- **回滚命令**（5 秒内完成）：
  ```bash
  # 1. 停 cron（注释掉 4 行 add_job）
  # 2. 删端点（注释 5 个 @router.get）
  # 3. DROP 5 张表（按外键逆序）
  DROP TABLE IF EXISTS datasource_health, llm_cache, market_index_snapshot, hotmoney_snapshot, quote_snapshot;
  ```

## 九、验收清单

- [ ] `python -m py_compile backend/app/datasource/sources.py` 通过
- [ ] `python -m py_compile backend/app/services/{quote,hotmoney,market_index}_snapshot.py backend/app/services/llm_cache.py` 通过
- [ ] `tsc --noEmit` 0 错
- [ ] 8 个新测试全过
- [ ] 浏览器复现 8/20 13:24 场景：连续点持仓监控 10 次，0 报错
- [ ] curl `/api/system/datasource-health` 返回 5 个数据源（akshare_main / sina_fallback / tencent_fallback / llm_cache / sector_refresh）状态 closed
- [ ] 手工制造 akshare 失败（断网/重定向）后 60s 内看到 datasource_health 变 open，接口仍能返回 stale cache
- [ ] OverviewPage 数据源健康度卡片显示 5 源状态

## 十、改造后预期效果

| 指标 | 改造前 | 改造后 |
|---|---|---|
| 持仓监控页失败率 | ~5%（偶发 15s 超时） | < 0.5%（DB 读秒回） |
| 游资追踪页失败率 | ~14% | < 1% |
| 大盘指数刷新延迟 | 实时（直连，慢） | ≤ 60s（DB 读，秒回） |
| LLM 重复推理率 | 0 | 0（24h 缓存命中） |
| 数据源故障定位 | 翻日志猜 | 监控面板直查 |

---

## 十一、Claude Code 执行边界

✅ **应该做**：
- 复用 `sector_snapshot` 已验证模式（lazy import 规避循环、AUTO_INCREMENT + String(10) DDL、断路器 + cron */5）
- 新增 5 张表必须跑 `init.sql` 迁移，并验证 `Base.metadata.create_all` 兼容
- 8 个新测试覆盖：断路器 closed→open→half_open 转移、降级链全失败抛错、缓存命中、stale 判断、cron 触发、监控端点
- 改前端时只动 `web/src/`，不动 `streamlit/`

❌ **不应该做**：
- 不要新建 Agent（8 业务 + 2 辅助已固定，不超载）
- 不要碰交易规则表 / 研判标准表（红线）
- 不要混用 SQLite 与 MySQL 语法
- 不要把 `safe_fetch` 改成异步（项目目前用同步栈）
- 不要在 `web/src/api/client.ts` 之外加 retry 逻辑（统一在 client.ts 收口）

---

## 十二、Claude Code 交付

按惯例回 3 件套：
1. 修改文件清单（实际改的路径 + 行号）
2. 8 测试通过截图或输出
3. **重点**：告诉 sir 这个改造**永久消除"网络错误"这个伪报错**——因为前端永远读 DB 快照，DB 总是可用的，axios 永远 200
