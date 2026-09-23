# 买卖点信号体系 · 批 1 执行指令（基建）

> **生成**：Lark（WorkBuddy）｜**执行**：Codex CLI / Claude Code / DSH｜**决策人**：sir
> **上游方案**：`D:\self\买卖点信号体系_方案.md` —— 本指令用「参见 §X」引用，**禁止整读方案**（只 grep 定位节）
> **性质**：仅含需求 + 规则 + 约束，不含代码
> **工作目录**：`D:\self`（所有 path 相对此目录）

---

## 0. 元信息

| 项 | 内容 |
|---|---|
| 批次 | 批 1 / 共 3 批（本批只做基建） |
| 工时预估 | 1.5 ~ 2 天 |
| 依赖 | 无（可与「因子细分化」批 2 并行，互不干扰） |
| 决策依赖 | **无** —— 方案 §11 的 3 个阈值（55% / 1.5 / 10 日窗口）只在批 2 统计时用到，本批不涉及 |

---

## 一、目标

建买卖点信号体系的**基建层**，产出"每日全市场信号触发数据"。

- **要做**：指标层扩展（复用 `services/indicator.py`）+ 信号注册表 + 22 条信号函数 + 全市场扫描 job + `signal_trigger` 表
- **不做**：统计、报告、UI、Agent 注入 —— 均属批 2 / 批 3
- **核心原则**：**只攒数据，不出结论、不进任何 Agent**

---

## 二、架构约束

### 2.1 新建 / 改动清单（行数预算）

| 文件 | 类型 | 预算 |
|---|---|---|
| `backend/app/services/indicator.py` | **改** | +45（**仅追加** `boll` / `kdj` / `donchian` 三个数学函数） |
| `backend/app/indicators/core.py` | 删除/重写 | ≤50（信号快照聚合层：**只 import，函数名 `compute_signal_snapshot`**） |
| `backend/app/indicators/__init__.py` | 新建 | ≤10 |
| `backend/app/indicators/candle_patterns.py` | 新建 | ≤100 |
| `backend/app/services/signal_registry.py` | 新建 | ≤70 |
| `backend/app/signals/__init__.py` | 新建 | ≤10 |
| `backend/app/signals/position.py` | 新建 | ≤60 |
| `backend/app/signals/momentum.py` | 新建 | ≤70 |
| `backend/app/signals/breakout.py` | 新建 | ≤45 |
| `backend/app/signals/pattern.py` | 新建 | ≤55 |
| `backend/app/signals/volume.py` | 新建 | ≤35 |
| `backend/app/services/signal_scan.py` | 新建 | ≤130 |
| `backend/app/db/models.py` | 改 | +40 |
| `backend/app/scheduler/jobs.py` | 改 | +20 |
| `backend/tests/test_signal_registry.py` | 新建 | ≤150（30 例） |
| **合计** | | **≤890** |

### 2.2 解耦铁律（死守）

- **不碰** `factors/*.py`、`services/factor_registry.py`、任何因子表
- **不碰** K 红线体系、C1-C3 阈值（60%/30%/0.92）、研判标准表
- **不碰** `take_profit.py` / `red_line_check.py` / `plan_quant.py` / `candidate_tradeable.py`
- **不新增任何交易动作**——本体系只做记录
- **不引新库**——只用 numpy / pandas / pydantic
- **不建第二套指标实现**——指标算法只写在 `services/indicator.py`；`indicators/core.py` 只做 import 聚合、不得定义算法（见 §3.2）

---

## 三、规则（不能省）

### 3.1 数据流顺序（必须照此实现）

```
扫描层拉一次日线 → 调一次 compute_signal_snapshot() → 得 features 字典
  → 把 (features, kline_df, code) 传给每一条信号函数 → 收集 hit=True → 落表
```

**禁止每条信号各自调用指标内核**（22 条各调一次 = 22 倍重复计算）。

### 3.2 指标层（**分层：数学库唯一 + 聚合层只组装**）

🔴 **唯一性铁律**：任何指标算法在全系统**只能有一份实现**。唯一性针对「**算法的实现**」，不是「文件个数」。

| 文件 | 职责 | 允许内容 |
|---|---|---|
| `backend/app/services/indicator.py` | **指标数学库 · 唯一实现源** | 已有 `sma`/`ema`/`macd`/`rsi`/`atr`/`rolling_extreme` + **快照函数 `compute_indicators(df)`（line 69，勿动勿复制）**；本批**仅追加 3 个数学函数**：`boll(close, 20, 2)` → 上/中/下轨 + %B、`kdj(high,low,close, 9,3,3)` → K/D/J、`donchian(high,low, window)` → 上下轨。MA5/MA60/5日均量**已存在**（`sma(close,5)` / `sma(close,60)` / `compute_indicators` 内 `volume_ratio_5`），**禁止重写** |
| `backend/app/indicators/core.py` | **信号快照聚合层** | **只允许 `import` 上述库函数** + 取最新值/前值 + 组装 dict。函数名固定为 **`compute_signal_snapshot(kline_df) -> dict`**（不得命名为 `compute_indicators`，避免与库内同名函数冲突）。**禁止定义任何指标算法** |

**硬约束**：

- `core.py` 必须 `from app.services.indicator import ...`，**禁止**自写 `_ema` / `_rsi` 或手算 MACD / ATR
- **口径一律以 `services/indicator.py` 为准**，含其边界行为（如 `rsi()` 缺失时 `fillna(50.0)`，**不得**改成 `NaN`）
- 已有函数（`sma`/`ema`/`macd`/`rsi`/`atr`/`rolling_extreme`/`compute_indicators`）的签名与实现**不得改动**
- `compute_signal_snapshot(kline_df)` 输出必须含：`latest_close` / `ma20` / `macd_dif` / `macd_dea` / `volume_ratio_5`，以及各指标的 `prev_*` 前值（如 `prev_macd_dif` / `prev_macd_dea` / `prev_ma20`）
- **纯函数**：同 input 必同 output，无随机、无 IO、无全局状态；数据不足 → 返回 `None`，不抛异常

### 3.2a ⚠️ 已落盘文件必须修正（上一轮遗留）

上一轮已落盘的 `backend/app/indicators/core.py`（85 行，**已删除重写，见 §4.2 步骤 2**）犯了两处错：

**错 1 · 自写指标算法**（未复用库）——已产生**实际口径分歧**：

| 指标 | `services/indicator.py`（准绳） | 当前 `core.py`（错） |
|---|---|---|
| EMA | `ewm(span, adjust=False)` — 无 `min_periods` | `ewm(..., min_periods=window)` — 有 |
| RSI | 缺失时 `fillna(50.0)` | 缺失时 `NaN` |
| ATR | `ewm(alpha=1/14, adjust=False)` | `ewm(..., min_periods=14)` |

**错 2 · 重复已有快照函数**——`services/indicator.py:69` **早已有 `compute_indicators(df)`**，返回 `latest_close`/`ma5-60`/`macd_*`/`rsi14`/`atr14`/`high_20d`/`volume_ratio_5`/`recent_klines`。`core.py` 里的同名 `compute_indicators` 属**重复实现**，违反唯一性铁律。

**修正要求（§4.2 步骤 2 具体执行）**：
1. **删除** `backend/app/indicators/core.py`，重写为新文件
2. 新文件只做：`from app.services.indicator import sma, ema, macd, rsi, atr, rolling_extreme, boll, kdj, donchian` → 定义 `compute_signal_snapshot(kline_df) -> dict`
3. 快照内容 = **库内 `compute_indicators()` 已有字段直接取用**（不重算）＋ 本批新增指标的 latest/prev 值

**已落盘的其余 4 个文件保留、不重做**：`indicators/__init__.py`、`indicators/candle_patterns.py`、`signals/__init__.py`、`services/signal_registry.py` —— 先核对是否符合本指令，符合则沿用，不符合则就地改。

### 3.3 信号注册表与清单

- `SignalDef` / `SignalResult` 字段定义：**参见方案 §4.1**（`status` 默认 `candidate`）
- 22 条信号的 ID、名称、触发条件、参数、方向：**参见方案 §3**（位置 5 / 动量 6 / 突破 4 / 形态 5 / 量价 2）
- 注册表风格对齐 `services/factor_registry.py`（装饰器 `@register` + `list_active()`）
- `min_bars = 250`；K 线不足 → 返回 `hit=False`，不报错
- 计算异常 → `reason="error:xxx"`，**不抛出**，不阻断扫描
- 参数硬编码在 `SignalDef` 内，**本批不做参数寻优**

### 3.4 数据获取（⚠️ 有一处同名函数陷阱）

| 用途 | 正确调用 | 说明 |
|---|---|---|
| 个股日线 | `get_datasource().fetch_daily_kline(code, start, end)` | 返回 DataFrame，**默认 `adjust="qfq"` 前复权，不要传其他值** |
| 股票池 | `source.fetch_spot_universe()` | `agents/discover.py:83` 的用法 |
| 交易日闸门 | `market_hours.is_trading_day()` | `datasource/market_hours.py:29` |

**🔴 禁用 `repo.fetch_daily_kline`**（`backend/app/db/repo.py:2513`）——它返回 `list[dict]` 且**只保留 date/open/high/low/close/volume 六列**，会丢掉涨停判定所需的 `change_pct`。

并行扫描参照 `agents/discover.py:293-315` 的 `ThreadPoolExecutor` + `_PARALLEL_MIN` / `_PARALLEL_MAX` 模式。

### 3.5 落表规则

- 表 `signal_trigger`：字段定义**参见方案 §4.2**
- 唯一约束 `(trade_date, stock_code, signal_id)` —— 重复写入自动跳过（幂等）
- `limit_up`：`change_pct >= 限制幅度 − 0.3%`；限制幅度 —— 主板 10 / 创业板·科创板 20 / ST 5 / 北交所 30
- `is_st`：股票名称含 `ST` 或 `*ST` → 1
- `dedup`：同一 `(stock_code, signal_id)` 在 **10 个交易日**内只记首次触发，后续触发写 `dedup=1`
- 停牌日**不记录**（无有效收盘价）
- 收益字段（`ret_*` / `excess_*` / `max_profit_20` / `max_drawdown_20` / `filled_at`）**本批全部留 NULL**，由批 2 回填
- 缺数据 → `NULL` + `reason`，**绝不编造**（K227）

### 3.6 扫描调度

在 `scheduler/jobs.py` 的 `start()` 内注册（风格对齐同文件既有 job）：

```
工作日 16:50 / id="signal_scan" / name="买卖点信号扫描"
replace_existing=True / misfire_grace_time=3600 / max_instances=1
```

- 函数**首行**做交易日闸门，非交易日直接 return
- 全市场分批（每批 ≤500 只），**批内** `ThreadPoolExecutor` 并发
- 单批失败不影响其他批；超时则记录已完成批次
- **目标总时长 ≤10 分钟**（全市场约 5000 只）

---

## 四、执行顺序（**含分段落盘协议，必须遵守**）

> **背景**：上一轮执行因长时间「只规划不落盘」，连接中断后 **1 小时 44 分的产出全部丢失**（零文件落盘）。以下协议直接针对此问题——**这是确保目标落地的手段，不是降低目标**。

### 4.1 分段落盘协议（硬约束）

- 每完成**一个文件**立即 Write 落盘，**严禁全部规划完再一次性写**
- 每个文件落盘后立即自检：模块可 import + 关键函数可调用
- 一个模块做完立即落盘，再进入下一个模块
- **断点续跑**：会话中断后重开，**先列目录 + `git status` 确认已落盘文件，从断点继续，严禁重做已完成部分**

### 4.2 步骤

0. **核对已落盘文件**（`indicators/__init__.py` / `indicators/candle_patterns.py` / `signals/__init__.py` / `services/signal_registry.py`）：符合本指令则沿用，不符合则就地改，**不重做**
1. `services/indicator.py` **仅追加 3 个数学函数**：`boll` / `kdj` / `donchian`（**已有函数一律不动**）→ **落盘 + 自检**（`python -c "from app.services.indicator import boll, kdj, donchian"`）
2. **删除并重写** `indicators/core.py` → 定义 `compute_signal_snapshot(kline_df) -> dict`：`import` 库函数 + 复用库内 `compute_indicators()` 已有字段 + 补 latest/prev（详见 §3.2a）→ **落盘 + 自检**
3. `services/signal_registry.py` 完善（对齐 `factor_registry.py` 风格）→ 落盘 + 自检
4. `signals/position.py`（s01-s05）→ 落盘 + 自检
5. `signals/momentum.py`（s06-s11）→ 落盘 + 自检
6. `signals/breakout.py`（s12-s15）→ 落盘 + 自检
7. `signals/pattern.py`（s16-s20）→ 落盘 + 自检
8. `signals/volume.py`（s21-s22）→ 落盘 + 自检
9. `db/models.py` 新增 `signal_trigger` 表（本批只需这一张；`signal_stats` 属批 2）→ 落盘 + 迁移自检
10. `services/signal_scan.py`（全市场扫描 + 落表）→ 落盘 + 自检
11. `scheduler/jobs.py` 注册 cron job → 落盘
12. `tests/test_signal_registry.py`（30 例）→ 落盘 + 跑通

---

## 五、验证清单

- [ ] 22 条信号均可独立调用，返回合法 `SignalResult`
- [ ] `compute_signal_snapshot()` 的 `macd_dif` / `macd_dea` **能被 `f02_macd_state` 正确读取**（口径一致性验证）
- [ ] `indicators/core.py` **无任何指标算法**：`grep -nE "ewm\(|rolling\(|\.diff\(|\.clip\(" backend/app/indicators/core.py` **应零命中**
- [ ] `services/indicator.py` 的已有函数（`sma` / `ema` / `macd` / `rsi` / `atr` / `rolling_extreme` / `compute_indicators`）**未被改动**（`git diff` 逐条核对）
- [ ] 单只票扫描 < 200ms
- [ ] 连续 3 个交易日扫描无异常、无 traceback
- [ ] 表内记录数 = 实际触发数（无重复、无遗漏）
- [ ] 停牌日无记录；涨停日 `limit_up=1`；ST 股 `is_st=1`
- [ ] 同一信号连续触发时 `dedup` 标记正确
- [ ] 非交易日 job 直接 return，不产生任何记录
- [ ] `pytest backend/tests/test_signal_registry.py` 全通过

---

## 六、红线

**业务红线**（同方案 §9）：

1. 不碰因子体系（`factors/*` / `factor_registry.py` / 因子表）
2. 不碰 K 红线、C1-C3 阈值、研判标准表
3. 不碰 `take_profit.py` / `red_line_check.py` / `plan_quant.py` / `candidate_tradeable.py`
4. **不新增交易动作**——只记录，绝不下单、绝不改仓位
5. 新信号默认 `candidate`，未经 sir 拍板不得设为 `active`，不得注入任何 Agent
6. 不引新库
7. 数据缺失不编造（K227）
8. 无未来函数——任何计算只用当日及之前数据
9. **不自动 commit / push** —— 完成后报告 sir
10. 不顺手改其他文件——改动限于本指令 §2.1 清单
11. 信号状态变更须写 `review_log`（本批无状态变更，仅约束后续）
12. **禁止第二套指标数值计算**——所有指标算法只写在 `services/indicator.py`；`app/indicators/` 下**只允许** `candle_patterns.py`（K 线形态识别，非指标数值）与 `core.py`（聚合层，仅 `import` 组装）；**严禁**自写 `_ema` / `_rsi` / 手算 MACD / ATR / 重复实现 `compute_indicators`
13. **分段落盘不可省**：每个文件写完立即落盘，严禁攒到最后一次性写（上一轮零落盘的直接教训）

**省 token 约束**：

1. 不复读本指令已固化信息，不整读方案（只 grep 定位节）
2. 不写超出 §2.1 清单的代码
3. 函数 docstring ≤3 行，函数体内不写注释
4. 复用已有函数（`get_datasource` / `fetch_spot_universe` / `market_hours`）
5. 测试用例不超过 30 个
6. 执行完毕报告 ≤10 行：①改了什么（`path:line`）②测试结果 ③遗留风险

**改动行数预算**：合计 ≤890 行。超出 → **停下报告 sir**，不要自行加功能。
