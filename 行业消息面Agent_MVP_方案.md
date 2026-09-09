# 行业消息雷达（观察型 shadow 模式）方案

> ⚠️ **已被修订版取代 · 请勿作为实施依据**：本文件为 Lark 在收到复审结论后的二次修订尝试。第三方 AI 已产出更严谨的权威版本 `D:\self\行业消息面Agent_MVP_方案_修订版.md`（257 行，含 source_scope 区分 / 多行业映射 / status 枚举 / K228 无脆弱阈值 / shadow 三层指标）。**实施请以修订版为准**，本文件仅作历史归档。

> **关联**：立项评估 `D:\self\行业消息面Agent_立项评估.md`（已按复审同步修订）
> **决策人**：sir
> **方案日期**：2026-09-07
> **复审状态**：条件通过（2026-09-07 14:00），本版为按复审意见修订版
> **核心定位**：**观察型行业消息雷达**——只观察、只记录、只验证，**不接正式 Agent、不进候选池、不改评分**。跑出"消息解读是否有预测力"的真实数据后，再决定是否升级为候选池弱特征。

---

## 一、目标与边界

### 1.1 目标（修订）

做一个**独立的 shadow（影子）验证闭环**，回答一个可量化的问题：

> "行业消息 → LLM 解读方向 → 未来 T+1/3/5 行业板块涨跌"，这条链路到底有没有预测力？

具体产出：
1. 行业消息聚合（**诚实标注信号类型**，见 §4.1）
2. LLM 对"消息 → 行业影响"的解读（只解读、不推荐买卖）
3. **shadow 验证闭环**：每条解读记录板块指数点位 + T+1/3/5 回填涨跌幅，算方向命中率
4. 观察型前端页面（只读 + 反馈 + 验证结果展示）

### 1.2 不做什么（修订，硬边界）

- ❌ **不进候选池**（Discover 候选列表不受任何影响）
- ❌ **不改评分**（Score 评分逻辑零改动）
- ❌ **不接正式 Agent**（不动 LangGraph、不动任何 collect 段）
- ❌ **不重复做单股新闻**（已有 announcement_service）
- ❌ **不做买卖推荐**（解读 ≠ 推荐，K228 红线）
- ❌ **不做实时推送**（飞书推送不在本方案）
- ❌ **不假装有"行业新闻"数据源**（当前 AKShare 只有成分股个股新闻，只能产出"代理信号"，见 §4.1）

---

## 二、架构

### 2.1 分层（修订：加 shadow 验证闭环）

```
[东财搜索 fetch_news（已有，单股维度）]
        │
        ▼ 成分股个股新闻（不重复入库，只读 news_article / 直接抓）
        │
  [+ 信号分类 signal_type + 行业字典映射]  ← 批 1
        │
        ├── signal_type = "constituent_proxy"（成分股代理信号，MVP 唯一产出）
        └── signal_type = "industry_news"（真正行业新闻，字段预留，MVP 不产出）
        │
        ▼
  [行业聚合 + content_hash 去重]
        │
        ▼
  [DeepSeek LLM 解读：仅行业影响 + K228 拦截]
        │
        ▼
  [sector_news_ai_interpret 表]
        │
        ▼
  [shadow 验证：记录板块指数点位 → T+1/3/5 回填涨跌幅 → 方向命中率]
        │
        ▼
  [观察型 React 页面（只读 + 反馈 + 验证结果）]
```

### 2.2 与现有系统的耦合点（唯一耦合：数据源，其他全隔离）

| 复用资产 | 复用方式 | 是否影响现有系统 |
|---|---|---|
| `akshare_source.fetch_news` (`akshare_source.py:1017`) | 直接调，已带 600s 缓存 + fallback | ❌ 无影响 |
| `akshare_source.fetch_industry_spot` (`akshare_source.py:1030`) | 行业字典 v1 数据源 + shadow 验证取板块指数 | ❌ 无影响 |
| `cache` 模块（项目 SimpleCache） | 复用 | ❌ 无影响 |
| DeepSeek LLM client（项目默认） | 复用 | ❌ 无影响 |

**关键**：本方案所有新表、新 service、新 API 完全独立，**不写任何现有表、不动任何现有 Agent/collect 段/prompt**。

---

## 三、数据库设计（修订：3 张 → 5 张）

### 3.1 新增 5 张表

**`sector_news_article`（行业消息雷达原始信号）**

字段：`id / signal_type / sector_code / sector_name / title / content / source / source_url / published_at / content_hash / stock_codes(JSON) / mapping_confidence / human_review_status / human_review_note / created_at / ttl_at`

**`sector_news_ai_interpret`（AI 解读）**

字段：`id / sector_code / sector_name / signal_type / source_news_ids(JSON,≤5) / summary / impact_direction / impact / quote_evidence(JSON) / information_score / confidence / k228_status / human_review_required / model_version / created_at`

**`sector_dict_v1`（行业字典 v1，固化）**

字段：`id / sector_code / sector_name / industry_keywords(JSON,≥5) / ttl / source(sector_daily/sector_snapshot/手工)`

**`sector_news_shadow_verify`（shadow 验证闭环，新增）**

字段：`id / interpret_id / sector_code / sector_name / signal_date / base_index_value / t1_return / t3_return / t5_return / t1_at / t3_at / t5_at / direction_correct / created_at`

**`sector_news_feedback`（用户反馈，新增，不直接改字典）**

字段：`id / news_id / interpret_id / feedback_type(dismiss/confirm/mislabel) / note / processed / created_at`

### 3.2 行业字典 v1 来源（不靠 LLM 自己说）

| 行业 | 关键词种子（来源 sector_daily.py 板块快照） |
|---|---|
| 新能源 / 锂电 / 光伏 | 锂、电池、电芯、储能、宁德、比亚迪、阳光电源、隆基... |
| 半导体 / 芯片 | 半导体、芯片、晶圆、光刻、封测、中芯、长存、寒武纪... |
| 医药 / 生物 | 药、医、临床、CRO、创新药、恒瑞、百济神州... |
| ... | ... |

**关键**：行业字典从 `sector_daily.py` 板块快照反推关键词种子 + **手工补充硬词**（如"宁德时代"="300750"+ 锂电关键词）。**LLM 与用户都无权直接修改字典**——所有变更走 §4.3 人工 review 流程。

---

## 四、业务规则（修订）

### 4.1 信号分类（本次修订核心）

| 信号类型 | 含义 | MVP 是否产出 | 数据源 |
|---|---|---|---|
| `constituent_proxy` | 成分股新闻代理信号（某行业成分股的个股新闻聚合） | ✅ 是（唯一产出） | AKShare `fetch_news`（单股） |
| `industry_news` | 真正行业新闻（产业政策/行业数据/部委发文等） | ❌ 否（字段预留） | 财联社电报/行业研报等，**不在 MVP** |

**诚实边界**：MVP 阶段所有信号一律标记 `constituent_proxy`，**绝不**把成分股新闻包装成"行业新闻"。`industry_news` 数据源是否接入，取决于 shadow 验证结果（§四.4）与 sir 后续拍板。

### 4.2 K228 红线（修订：三项精确定义）

新增 **K228 行业消息解读红线**，与 K189 同级管理：

1. **原文精确引用**：LLM 每条解读的 `quote_evidence` 必须包含**逐字原文片段**（exact quote，非转述），且每条 quote 附带 `evidence_locator`（第几段/第几句）。
2. **证据位置**：`evidence_locator` 必须能定位到 `sector_news_article.content` 的实际位置；定位不到 → 该条 quote 作废。
3. **推荐表达拦截**：LLM 输出含以下任一词 → 整条解读 `k228_status=blocked`，不入前端：
   `买入 / 卖出 / 加仓 / 减仓 / 建仓 / 清仓 / 目标价 / 止损 / 止盈 / 强烈推荐 / 建议持有`
4. **只限行业影响**：解读范围只限"行业层面影响"，不得扩散到个股买卖判断（行业影响归行业，个股决策属人工/Score Agent 范畴）。
5. **来源校验**：解读引用的 news_id 必须真实存在于 `sector_news_article`，否则拒绝入库。

### 4.3 用户反馈流程（修订：不直接改字典）

```
用户点"无效/误标" → 写入 sector_news_feedback（feedback_type + note）
        ↓
    人工定期 review（不自动）
        ↓
    确认误标 → 手动更新 sector_dict_v1（加/删关键词）
```

**关键**：用户反馈**只进 feedback 表**，不触发任何字典自动更新；字典变更必须人工 review 后手动执行。LLM 同理无权改字典。

### 4.4 shadow 验证闭环（本次修订核心新增）

| 步骤 | 动作 | 时机 |
|---|---|---|
| S1 | 每条解读入库时，记录 `base_index_value` = 该行业板块指数当日 close（来自 `fetch_industry_spot` / 板块历史 K） | 解读时 |
| S2 | T+1 交易日，回填 `t1_return`（%） | 每日 cron |
| S3 | T+3 交易日，回填 `t3_return`（%） | 每日 cron |
| S4 | T+5 交易日，回填 `t5_return`（%） | 每日 cron |
| S5 | 回填完成后计算 `direction_correct`（解读方向 vs 实际涨跌方向是否一致） | 回填时 |

**验证指标**（观察期 ≥ 3-4 周真实数据）：
- 方向命中率 = 方向正确条数 / 已回填总条数
- 信息量评分（information_score）与 |实际涨跌幅| 的相关性

### 4.5 数据源配额

- 单次扫描**最多 5 只成分股**（按 sector_dict_v1 + `fetch_industry_cons` 提供）
- 单股抓取间隔 ≥2s（防东财限流，复用 `_call_with_retry`）
- 全行业轮询**每天 1 次**（cron 早 8:00），单次最多覆盖 8 个行业
- 抓取的 news **不写 news_article**（只读），sector_news_article 单独存

---

## 五、API 设计（批 1 范围：3 个 + 2 个 cron）

| 端点 | 方法 | 入参 | 出参 | 用途 |
|---|---|---|---|---|
| `/sector-radar/list` | GET | `sector_code` / `days` / `signal_type` | 雷达信号列表（含解读 + 验证状态） | 前端主查 |
| `/sector-radar/interpret/run` | POST | `sector_code` / `news_ids` | 触发 LLM 解读 | 手动重跑 |
| `/sector-radar/feedback` | POST | `news_id` / `feedback_type` / `note` | 写反馈 | 用户标记 |
| `cron: sector_radar_worker()` | 后台 | 行业字典 + 时间 | 自动抓 + 解读 + 记 base_index | 每日 1 次 |
| `cron: shadow_verify_worker()` | 后台 | 待回填记录 | T+1/3/5 回填 + 方向判定 | 每日 1 次 |

**说明**：
- `/sector-radar/curator/*`（经验沉淀闭环）、`/sector-radar/push/feishu` 均**不在本方案**，视 shadow 验证结果再议。

---

## 六、前端设计（观察型）

### 6.1 位置

React 新版优先：`web/src/pages/NewsRadarPage.tsx`（独立新页）

左侧导航侧栏新增入口（与"市场研判 MarketIntelPage"同级，分类"决策辅材"）：
- 路径：`web/src/components/layout/Sidebar.tsx` 找同级位置
- 命名：**行业消息雷达（观察）**—— 明确标注"观察"

### 6.2 页面结构

| 区域 | 内容 |
|---|---|
| 顶部 banner | 红色警示：**"观察型功能 · 不进入候选池 · 不作为决策依据"** |
| 顶部筛选 | 行业 Select（sector_dict_v1）+ 信号类型 + 时间范围 |
| 左侧栏 | 行业列表 + 信号类型分布 + 方向命中率（shadow 验证结果） |
| 主区 | 该行业信号流 + AI 解读摘要 + K228 原文 quote + 证据位置 |
| 行级动作 | "无效/误标"按钮（写 feedback 表，不直接改字典） |
| 详情抽屉 | 点信号 → 720px Drawer，3 段（原文 / AI 解读含 quote / shadow 验证元信息） |

### 6.3 信号类型徽章（诚实标注）

| 类型 | 徽章 | 含义 |
|---|---|---|
| `constituent_proxy` | 灰色「代理信号」 | 成分股新闻聚合，非行业新闻 |
| `industry_news` | 蓝色「行业新闻」 | 真正行业新闻（MVP 不产出） |

### 6.4 shadow 验证结果展示

| 状态 | 显示 |
|---|---|
| 未回填 | 灰字「待 T+1/3/5」 |
| 方向命中 | 红（涨）/ 绿（跌）色数字 + 「命中」 |
| 方向未命中 | 灰字 + 「未命中」 |

> 颜色遵循 <regional_conventions>：**A 股涨→红、跌→绿**（区别于美股）。

---

## 七、批次拆解（修订）

### 批 1：观察型雷达 MVP（本次范围）

| # | 模块 | 工时 | 验收 |
|---|---|---|---|
| 1.1 | DB 5 表 + migration | 0.5 天 | `test_sector_radar_migration.py` |
| 1.2 | 行业字典 v1 种子（≥8 行业） | 0.5 天 | 8 行业覆盖 |
| 1.3 | `services/sector_radar.py`（抓取 + 信号分类 + 映射 + LLM 解读 + K228 + 入库） | 2 天 | `test_sector_radar.py` |
| 1.4 | API 路由（3 个 + 2 cron） | 0.5 天 | `test_sector_radar_routes.py` |
| 1.5 | shadow 验证闭环（base_index + T+1/3/5 回填 + 命中率） | 1 天 | `test_shadow_verify.py` |
| 1.6 | K228 红线（exact quote + evidence_locator + 推荐词拦截） | 0.5 天 | `test_k228_redline.py` |
| 1.7 | React 页面 `NewsRadarPage.tsx` + Sidebar 入口 | 1.5 天 | 手动跑通 |
| 1.8 | 端到端联调 + 全量 pytest | 1 天 | 全绿 |

### 批 2：验证评估（观察期后，**非本次范围**）

观察 3-4 周 shadow 验证数据 → 产出《行业消息雷达验证报告》→ 交 sir 拍板是否升级。**升级判据不预设数值**（不再写"≥5%"），由验证报告 + sir 判断。

### 批 3：可能的弱特征接入（视批 2 结论，非本次范围）

仅当验证显示有稳定预测力，才讨论：是否作为候选池**弱特征**（不改变评分主逻辑）、是否接 `industry_news` 数据源。

---

## 八、红线（与项目既有铁律一致）

| # | 红线 | 出处 |
|---|---|---|
| 1 | **不进候选池、不改评分、不接正式 Agent** | 本次铁律（复审强制） |
| 2 | 不重复做单股新闻 | 本次铁律 |
| 3 | LLM 只解读、不得推荐买卖 | 本次铁律（K228） |
| 4 | 行业字典固化，LLM + 用户都不可直接改 | 本次铁律（复审修订） |
| 5 | 信号类型诚实标注，不把代理信号包装成行业新闻 | 本次铁律（复审强制） |
| 6 | React 新版优先、Streamlit 不动 | 项目铁律（2026-08-20） |
| 7 | 单批 ≤ 150 行代码预算（不含前端/migration） | 项目铁律（2026-08-24） |

---

## 九、风险与兜底（修订）

| 风险 | 兜底 |
|---|---|
| 成分股新闻≠行业新闻，代理信号有偏 | 诚实标注 `constituent_proxy`；验证报告显式区分 |
| 行业字典覆盖不足 | 落 `news_unmapped` LOG + 人工补字典（§4.3 流程） |
| LLM 解读幻觉 | K228 三项拦截（exact quote + 证据位置 + 推荐词） |
| 东财限流 | 复用 `_call_with_retry` + 5 只成分股上限 + 2s 间隔 |
| shadow 验证样本不足 | 观察期 ≥ 3-4 周；样本不足时报告明确"样本量不足以结论" |
| 验证显示无预测力 | 停止推进，归档为"行业日历辅材"，不进决策主轴 |
| 观察期误用 | 前端顶部红色 banner + 页面命名标注"观察" |

---

## 十、不在本方案范围（明确说）

- 自动推送（飞书）
- 关联单股（"该新闻利好 XX 股"自动建议）
- `industry_news` 真正行业新闻数据源（财联社等）
- 行业聚类 / 主题聚类（只按行业字典匹配）
- 多 LLM provider 切换（只用 DeepSeek）
- 历史新闻批量回溯（只跑近 7 日窗口）
- 经验沉淀 curator/review/rollback
- 候选池接入 / 评分修改 / Agent 注入（批 2/3 视验证结果再议）
