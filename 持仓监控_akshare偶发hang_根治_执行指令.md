# holdings/quotes 偶发 hang + 前端 15s timeout 失败 —— 根治执行指令（v2 · 融合腾讯批量直连）

> **生成者**：Lark 助手（项目助理）
> **执行者**：Claude Code
> **决策人**：sir
> **背景**：2026-08-21 14:43 截图 + 实测 5 连测（详见 §〇）+ **参考"阿宝 claw 实战执行方案"（`qt.gtimg.cn` 腾讯批量直连，实测 5 只 0.56s）**——持仓监控页当前走 `fetch_spot_universe` 全市场 5000+ 只快照，akshare 单点 hang 10-20s，前端 axios 15s 抢先 timeout。
> **预期工时**：0.5 批次 / 0.5-1 天
> **依赖**：8/19 已落地的 `sector_snapshot` 模式 + `breaker.py` 阈值参数
> **回滚预案**：5 分钟内停 cron + 还原 breaker 配置 + 还原 timeout，零数据破坏

---

## 〇 排查实录（5 连测实证 2026-08-21 14:44 + 腾讯批量直连实测 14:59）

| 端点 | 实测 | 失败率 | 根因 |
|---|---|---|---|
| `/api/holdings` | 5-11ms × 5 | 0% | DB 直读，无数据源风险 |
| `/api/holdings/quotes` | **20s 截断 × 2 → 1.6s/1.4s/1.2s** | **40%** | `build_holding_view:52` 走 `fetch_spot_universe()` 全市场 5000+ 只，akshare `stock_zh_a_spot_em` 单点 hang 10-20s |
| `/api/market/indices` | 10.6s/10.8s/8s/**76ms**/**61ms** | 0% | 8/19 断路器生效——但阈值(3次)太高，前 3 次仍等满 hang |
| **腾讯 `qt.gtimg.cn/q=sh600487,sz002475,...`** | **0.56s（批量 5 只一次请求）** | **0%** | **新增首选源**：单请求批量拉持仓代码，绕开全市场快照 |
| **腾讯 K 线 `web.ifzq.gtimg.cn`** | **1.83s** | 0% | 备用 K 线源 |

**截图全 8 请求 time=15.00kr = axios `timeout: 15_000`（`web/src/api/client.ts:12`）**——后端 quotes 真实耗时 15+s，前端 timeout 抢先抛错。

**三大根因**：
1. **单源依赖**：持仓页只走 akshare 东财全市场快照，一个源挂了全挂（阿宝方案 P0 痛点①）
2. **无重试/连接复用**：akshare `_call_with_timeout` 每请求新建连接，无 Session 连接池（阿宝痛点②③）
3. **无 DB 兜底**：`fetch_spot_universe` 无落库，akshare 一挂就 0 数据返回

---

## 一 目标

让"持仓监控"页**任何情况下**都在 **5s 内拿到数据**，**首选腾讯 `qt.gtimg.cn` 批量直连持仓代码**（不是全市场），配「指数退避重试 + Session 连接池 + DB 快照 fallback」三层，**永久消除**单源 hang 拖整页 timeout。

**验收硬指标**：

- [ ] `/api/holdings/quotes` P95 < 2s（首选腾讯批量直连），**失败率 0%**
- [ ] `web/src/api/client.ts` GET 端点 timeout 15s → 25s
- [ ] 5 连测 quotes 全 < 3s（curl 20s 截断 0 次）
- [ ] 即使 akshare + 腾讯全挂 30 分钟，`/api/holdings` 仍能展示 quote_snapshot 兜底 + "行情已过期 X 分钟"标注
- [ ] 腾讯批量直连实测：持仓 N 只 = 1 次 HTTP 请求，耗时 < 1s

---

## 二 架构约束

| 对象 | 决策 | 理由 |
|---|---|---|
| **`tencent_quotes(code_list)`** | **新建**（`akshare_source.py` 同文件加方法） | **首选源**：`qt.gtimg.cn` 批量直连持仓代码，单请求拉全部，绕开全市场快照 |
| **`quote_snapshot` 表** | **新建** | DB 永久兜底（腾讯/东财全挂时用） |
| **`quote_snapshot_refresh_job`** | **新建** cron `*/5` | 与 sector_snapshot 同节奏落库 |
| **breaker 阈值** | 改 `datasource_breaker_threshold: 3 → 1`、`cooldown: 60→30` | 1 次失败即开，前 1 次不再拖 hang |
| **Session 连接池** | `akshare_source.py` 用 `requests.Session` 实例 | 复用连接 3-5x 提速 + 降反爬（阿宝方案） |
| **`holding_view.py`** | 改取数链：腾讯批量直连 → DB 快照 fallback | **不再裸调全市场快照** |
| **`web/src/api/client.ts`** | GET timeout 15s → 25s | 容忍后端重试 + 兜底链 |

**红线（不动）**：

- ❌ 不改 6 因子 / 交易规则 / scoring 阈值
- ❌ 不改 Streamlit 旧前端
- ❌ 不改 `experience_worker.py` / 经验沉淀 Worker
- ❌ 不在 `holding_view` 加任何研判/评分（只做"取数 + fallback"两层选择）
- ✅ 腾讯/eastmoney/新浪 URL 均为**实测可用的生产源**（阿宝已验证），不做假源

---

## 三 规则

### 3.1 腾讯批量直连（新增，首选源，`akshare_source.py` 方法）

```python
# akshare_source.py 内新增方法：腾讯 qt.gtimg.cn 批量实时行情（首选）
# 实测：N 只 = 1 次 HTTP，< 1s；返回 {"code": price, ...}
def fetch_tencent_batch(self, codes: list[str], timeout: int = 8) -> dict[str, float]:
    """腾讯批量实时最新价。优先级最高，替代 akshare 全市场快照。
    走 Session 连接池 + 指数退避3次。返回 {code: latest_price}，失败返回 {}。"""
    if not codes:
        return {}
    full = [f"{'sh' if c.startswith('6') else 'sz'}{c}" for c in codes]
    url = f"http://qt.gtimg.cn/q={','.join(full)}"
    # 复用 self.session（新建的 requests.Session）
    for attempt in range(3):
        try:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            text = resp.text
            out: dict[str, float] = {}
            for line in text.strip().split("\n"):
                import re
                m = re.match(r'v_(\w+)="([^"]+)"', line)
                if not m:
                    continue
                code_key = m.group(1).replace("sh", "").replace("sz", "")
                fields = m.group(2).split("~")
                if len(fields) < 6:
                    continue
                try:
                    out[code_key] = float(fields[3])
                except (TypeError, ValueError):
                    continue
            return out
        except Exception as exc:
            delay = min(1.0 * (2 ** attempt), 8.0)
            logger.warning("腾讯批量行情第%d次失败: %s，%.1fs后重试", attempt + 1, exc, delay)
            time.sleep(delay)
    return {}
```

**字段索引**（腾讯 `v_sh600487="1~name~code~price~prev_close~open~...~change_pct~..."`）：

| 字段 | 索引 |
|---|---|
| name | fields[1] |
| code | fields[2] |
| **price** | **fields[3]** |
| prev_close | fields[4] |
| open | fields[5] |
| volume | fields[6] |
| change_pct | fields[31]（涨跌幅%） |

### 3.2 holding_view 取数链（改 `build_holding_view()`）

```python
def build_holding_view() -> dict:
    now_min = time.strftime("%Y-%m-%d %H:%M")
    rows = repo.list_holdings(status="holding")
    if not rows:
        return {"rows": [], "quote_time": now_min, "quote_error": None,
                "total_capital": settings.total_capital}
    codes = [r["stock_code"] for r in rows]

    quote_error = None
    quotes: dict[str, float] = {}
    source = None
    ds = get_datasource()

    # ① 首选：腾讯批量直连（N 只 = 1 请求，< 1s）
    try:
        quotes = ds.fetch_tencent_batch(codes)
        if quotes:
            source = "tencent"
    except Exception as exc:
        logger.warning("腾讯批量行情失败: %s", exc)

    # ② fallback：DB quote_snapshot（10 分钟内有效）
    if not quotes:
        try:
            df = repo.get_quote_snapshot(within_minutes=10)
            if df is not None and not df.empty:
                quotes = {str(r["stock_code"]): float(r["price"])
                          for _, r in df.iterrows() if r["code"] in set(codes)}
                if quotes:
                    source = "snapshot"
        except Exception as exc:
            logger.warning("DB 快照行情失败: %s", exc)

    # ③ 最终 fallback：akshare 全市场快照（走断路器，akshare 挂时返回空不阻塞）
    if not quotes:
        try:
            quotes = _quote_map(ds.fetch_spot_universe())
            if quotes:
                source = "universe"
        except Exception as exc:
            logger.warning("全市场快照行情失败: %s", exc)
            quote_error = f"行情获取失败：{exc}"

    ...  # 其余逻辑不变
    return {"rows": out, "quote_time": now_min, "quote_error": quote_error,
            "source": source, "total_capital": settings.total_capital}
```

### 3.3 quote_snapshot 表 DDL（MySQL 8.0，仿 sector_snapshot）

```sql
CREATE TABLE IF NOT EXISTS quote_snapshot (
  id          INT PRIMARY KEY AUTO_INCREMENT,
  stock_code  VARCHAR(10) NOT NULL,
  name        VARCHAR(50),
  price       DECIMAL(10,3),
  change_pct  DECIMAL(8,3),
  source      VARCHAR(20) NOT NULL DEFAULT 'tencent',  -- 'tencent'/'eastmoney'/'universe'/'stale'
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_stock (stock_code),
  KEY idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 3.4 quote_snapshot 刷新策略

- cron `*/5`（每 5 分钟，9:00-15:00 交易时段），仿 `sector_refresh_job`
- `refresh_quote_snapshot()` 流程：
  1. 先 `fetch_tencent_batch(codes from holdings)`（腾讯）
  2. 腾讯失败 → `fetch_spot_universe()`（东财全市场）兜底
  3. 落 `quote_snapshot` 表（整表覆盖）
  4. 失败不抛，`logger.warning`

### 3.5 Session 连接池（`akshare_source.py` `__init__` 加）

```python
import requests
# __init__ 内：
self.session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
self.session.mount("http://", adapter)
self.session.mount("https://", adapter)
self.session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
})
```

### 3.6 breaker 阈值（改 `app/core/config.py`）

```python
datasource_breaker_threshold: int = 1   # 1 次失败即开断路器
datasource_breaker_cooldown: int = 30   # 30s 冷却
```

### 3.7 前端 timeout（改 `web/src/api/client.ts:12`）

```ts
const api = axios.create({ baseURL: '/api', timeout: 25_000 })  // 原 15_000
```

`apiPost/apiOcr/apiUpload` 三个实例**不动**。

---

## 四 实现参考

| 文件 | 用途 | 风格参照 |
|---|---|---|
| `backend/app/datasource/akshare_source.py` | **新增** `fetch_tencent_batch()` + `requests.Session` | 仿阿宝 `ProductionDataFetcher`，但只加批量实时，不加整套类 |
| `backend/app/services/holding_view.py` | 改 `build_holding_view()` 取数链 | 三段 fallback：腾讯→DB→全市场 |
| `backend/app/services/quote_snapshot.py` | **新建** 服务，cron 落库 | 仿 `sector_snapshot.py` |
| `backend/app/db/repo.py` | 加 `upsert_quote_snapshot()` / `get_quote_snapshot()` | 仿 `upsert_sector_snapshot()` |
| `backend/app/scheduler/jobs.py` | 注册 `quote_snapshot_refresh_job` | 仿 `sector_refresh_job` |
| `backend/app/core/config.py` | 改 2 个 breaker 默认值 | 单行修改 |
| `init.sql` | 加 `quote_snapshot` DDL | 仿 `sector_snapshot` DDL |
| `web/src/api/client.ts` | GET timeout 25_000 | 单行修改 |

**关键契约（Claude Code 可自由重写，但签名不变）**：

- `fetch_tencent_batch(codes: list[str], timeout: int = 8) -> dict[str, float]`
- `refresh_quote_snapshot() -> dict`
- `repo.upsert_quote_snapshot(rows: list[dict]) -> int`
- `repo.get_quote_snapshot(within_minutes: int) -> pd.DataFrame | None`
- `build_holding_view()` 入参/返回结构零变（新增 `source` 字段可加，前端兼容）

---

## 五 执行顺序

1. **改配置**（`config.py`）—— breaker 阈值 3→1、冷却 60→30
2. **新增 `fetch_tencent_batch()`**（`akshare_source.py`）+ `requests.Session` —— 阿宝方案核心，`qt.gtimg.cn` 批量
3. **新建 `quote_snapshot` 表** + `repo.upsert_quote_snapshot()` / `get_quote_snapshot()`
4. **新建 `quote_snapshot.py`** 服务 + 注册 cron `*/5`
5. **改 `holding_view.build_holding_view()`** —— 腾讯→DB→全市场 三段 fallback
6. **改 `web/src/api/client.ts:12`** —— GET timeout 25s
7. **`init.sql`** 同步 DDL
8. **重启后端 + 验证 5 连测**（curl 5 次全 < 3s）
9. **git commit**

---

## 六 验证清单

- [ ] `fetch_tencent_batch(["600487","002475"])` 返回 `{"600487": 62.18, "002475": 54.65}`（实测字段价格正确）
- [ ] 腾讯批量直连耗时 < 1s（单请求拉全部持仓）
- [ ] `/api/holdings/quotes` 5 连测 P95 < 2s（修复前 40% timeout）
- [ ] `quote_snapshot` 表落库成功，cron 每 5 分钟更新 `updated_at`
- [ ] 停腾讯源（hosts 劫持 `qt.gtimg.cn`）→ `/api/holdings` 自动切 DB 快照，< 2s 返回，`source='snapshot'`
- [ ] 停腾讯 + 清空 DB 快照 → 走全市场快照 `source='universe'`，akshare 挂时 `quote_error` 非空但不阻塞
- [ ] 前端 `client.ts:12` timeout = 25_000
- [ ] `git diff` 仅限：`config.py` / `akshare_source.py` / `holding_view.py` / `client.ts` / `quote_snapshot.py`(新) / `repo.py` / `jobs.py` / `init.sql`
- [ ] `git diff` **不出现**：`scoring.py` / `score_prompt.py` / `HARD_RULES` / `red_line_*` / `streamlit/pages/*` / `experience_worker.py`
- [ ] `pytest tests/test_datasource_stability.py -k "tencent or quote_snapshot"` 全绿
- [ ] 手动断腾讯 30 分钟：`quote_snapshot.source='snapshot'` + 前端"行情已过期 X 分钟"

---

## 七 红线（sir 8/19 拍板铁律）

- auto-merge 永不修改交易规则/研判标准表
- 不预测涨跌幅/目标价/概率百分数（腾讯字段只采 raw 价，不解读）
- 不改 6 因子权重
- 不改 Streamlit
- 不改经验沉淀 Worker
- Agent 解耦：不在 holding_view 加研判/评分（只取数 + fallback）

---

## 附：阿宝方案核心要点（已融合进 §3.1/3.5）

| 阿宝痛点 | 阿宝方案 | 本指令落地 |
|---|---|---|
| ①单源依赖 | 腾讯→东财→新浪 多源切换 | `fetch_tencent_batch` 首选 + DB 快照 + 全市场 3 段 |
| ②无重试 | `retry_with_backoff` 指数退避 | `fetch_tencent_batch` 内 3 次退避循环 |
| ③无连接复用 | `requests.Session` + HTTPAdapter 连接池 | `akshare_source.__init__` 加 pool_connections=10 |
| ④反爬/限频 | User-Agent + 频率控制 | Session headers 带 UA + timeout 8s 内完成，加载自然控频 |

**腾讯源稳定性排序**（阿宝实测，已采用）：
`qt.gtimg.cn`（实时，⭐⭐⭐⭐⭐ 首选）> `web.ifzq.gtimg.cn`（K线）> `push2his.eastmoney.com`（备用）> `hq.sinajs.cn`（兜底，需 Referer）
