# 行业消息雷达（观察型 shadow 模式）批 1 - Claude/DSH 执行指令

> ⚠️ **已被修订版取代 · 暂不执行**：本文件为 Lark 在收到复审结论后的二次修订尝试。第三方 AI 已产出更严谨的权威版本 `D:\self\行业消息面Agent_批1_MVP_修订版执行指令.md`（122 行，含开工前确认 / 必备字段 / K228 无脆弱阈值 / 停止条件清单）。**执行请以修订版为准**，本文件仅作历史归档。

> **关联方案**：`D:\self\行业消息面Agent_MVP_方案_修订版.md`（权威）
> **关联评估**：`D:\self\行业消息面Agent_立项评估.md`（已同步去数字）

## §0 元信息

- 生成者：Lark（基于 sir 立项决策 + 第三方 AI 复审结论）
- 执行者：Claude Code / DSH
- 决策人：sir
- 工作目录：`D:\self`
- 原则：**观察型 shadow 模式**——不进候选池、不改评分、不接正式 Agent（方案 §1.2）

## §一 目标

**观察型行业消息雷达 MVP（周内上线）**：5 张表 + 1 个 service + 3 个 API + 2 个 cron + 1 个 React 页面 + shadow 验证闭环 + K228 红线，跑通"抓 → 信号分类 → 解读 → 记录指数点位 → T+1/3/5 回填 → 展示" 闭环。**只观察、只验证、零决策影响**。

学完内容：方案 §七 批 1 拆解（1.1-1.8 共 8 个子任务）。

## §二 架构约束

- **新文件**：`backend/app/services/sector_radar.py`、`backend/app/services/sector_dict.py`、`backend/tests/test_sector_radar.py`、`backend/tests/test_shadow_verify.py`、`backend/tests/test_k228_redline.py`、`web/src/pages/NewsRadarPage.tsx`
- **新表（5 张）**：`sector_news_article / sector_news_ai_interpret / sector_dict_v1 / sector_news_shadow_verify / sector_news_feedback`（方案 §3.1）
- **新路由**：`/sector-radar/list`、`/sector-radar/interpret/run`、`/sector-radar/feedback`、`cron: sector_radar_worker`、`cron: shadow_verify_worker`（方案 §五）
- **硬隔离**：不动任何现有 Agent/collect 段/prompt；**不写 `news_article` 表（只读）**；不动 `announcement_service.py` / `akshare_source.py` 的 `fetch_news` 调用方式
- **复用**：`fetch_news` (`akshare_source.py:1017`)、`fetch_industry_spot` (`akshare_source.py:1030`)、`fetch_industry_cons` (`akshare_source.py:1040`)、`cache`（SimpleCache）、DeepSeek LLM client
- **React 新版**优先；不动 Streamlit 的 `streamlit/pages/`

## §三 规则

**信号分类（方案 §4.1，本次核心）**：
- 每条 `sector_news_article` 记录 `signal_type` 必填，MVP 一律填 `constituent_proxy`
- `industry_news` 值仅作字段预留，MVP **不产出**、不抓取该类型数据源

**字段口径（方案 §3.1）**：
- `content_hash`：title + published_at + source 的 sha256 前 16 位，用于去重
- `mapping_confidence`：行业关键词命中数 / 标题分词数，0-1 浮点
- `human_review_status`：默认 `pending`，可选 `confirmed` / `rejected`
- `source_news_ids`：JSON list，长度 ≤ 5

**行业字典 v1（方案 §3.2）**：
- 种子来源 `fetch_industry_spot()` 板块列表 + 手工硬词（"宁德=300750" 等），≥8 行业
- **LLM 与用户都无权直接改字典**（反馈只进 `sector_news_feedback` 表，人工 review 后手动改）

**K228 红线（方案 §4.2，三项精确定义）**：
- `quote_evidence` 每条必须含 `{quote: 逐字原文, evidence_locator: 第几段/第几句}`
- `evidence_locator` 定位不到原文 → 该 quote 作废
- 输出含 `买入/卖出/加仓/减仓/建仓/清仓/目标价/止损/止盈/强烈推荐/建议持有` 任一 → `k228_status=blocked`，不入前端
- 解读只限行业影响，扩散到个股买卖 → blocked

**shadow 验证闭环（方案 §4.4，本次新增）**：
- 解读入库时记 `base_index_value` = 行业板块指数当日 close
- `shadow_verify_worker` 每日回填 `t1_return/t3_return/t5_return`（%），回填后算 `direction_correct`
- 方向判定：`impact_direction ∈ {利好,利空}` 且与涨跌幅方向一致 → True；`中性/无法判断` → 不参与命中率

**调用配额（方案 §4.5）**：
- 单次扫描 ≤ 5 只成分股；单股间隔 ≥2s（`time.sleep(2)`）
- cron 每天 1 次（08:00），全市场 ≤ 8 个行业

## §四 执行顺序

| # | 步骤 | 关键参考 |
|---|---|---|
| 1 | DB migration（5 表 + 索引） | 参考 `models.py:297 NewsArticle` 字段风格 |
| 2 | `services/sector_dict.py`：反推 + 手工硬词 → seed 到 sector_dict_v1 | ≥8 行业 |
| 3 | `services/sector_radar.py`：抓取 + signal_type 分类 + content_hash 去重 + 映射置信度 + LLM 解读 + K228 + 入库 | 复用 `get_recent_news` (`repo.py:1172`) |
| 4 | shadow 验证：解读时记 base_index + `shadow_verify_worker` 回填 T+1/3/5 + 方向判定 | 复用 `fetch_industry_spot` 取指数 |
| 5 | API 路由：`/sector-radar/list` + `/interpret/run` + `/feedback` | 参考 `routes.py:1995 experience_pending` 风格 |
| 6 | 2 个 cron job 到 `scheduler/jobs.py` | 参考 sector_daily/sector_snapshot cron 写法 |
| 7 | K228 校验函数 `_enforce_k228(parsed)`：exact quote + evidence_locator + 推荐词拦截 | 独立函数 |
| 8 | `web/src/pages/NewsRadarPage.tsx` + Sidebar 入口 + 顶部红色警示 banner | 复用 `@/api/` 新建 sectorRadar 调用 |
| 9 | 测试：`test_sector_radar.py`(4-5) + `test_shadow_verify.py`(2) + `test_k228_redline.py`(2) | 参考 `test_datasource_news.py` mock 风格 |
| 10 | 全量 pytest | 原有 567 测试不挂 |

## §五 红线

1. **不进候选池、不改评分、不接正式 Agent**（复审强制，违反即废）
2. **signal_type 诚实标注**，MVP 只产出 `constituent_proxy`，不包装成行业新闻
3. **LLM 输出必带 exact quote + evidence_locator**（K228）
4. **LLM 输出含推荐词 → blocked**（K228）
5. **行业字典固化**，LLM + 用户都不可直接改（反馈只进 feedback 表）
6. **不写 `news_article` 表**（只读，避免污染个股维度）
7. **不动 Streamlit**（React 新版优先）
8. **不改 `tradeable_view` / `repo.add_news` / `fetch_news` 已有逻辑**

### Claude Code 端省 token 6 条

| # | 手段 | 怎么做 |
|---|---|---|
| 1 | 不复读方案/评估 | 已读 → 只 grep 关键标识确认行号 |
| 2 | 不写超出范围代码 | 10 步就只动这 10 步相关文件 |
| 3 | 不写大段注释 | docstring ≤ 3 行；函数体内不写 `#`（除 K228/shadow trade-off） |
| 4 | 复用已有函数 | `fetch_news`/`get_recent_news`/`cache`/`fetch_industry_spot` 直接调 |
| 5 | 测试用例不超 | §四.9 已列数 → 只写 N 个 |
| 6 | 报告精简 | ≤ 10 行：①改了什么 ②测试结果 ③遗留风险 |

### 代码侧最小改动铁律

- 改动行数预算（不含 React 页面 / 不含 migration）：**≤ 150 行**
- 超出 → 停下报告 sir，不自行加功能

---

**开工前 `ls D:\self\行业消息面Agent_MVP_方案.md` 确认方案在位；commit 前缀 `sector-radar(批1)`，独立分支 `feature/sector-radar-shadow`。**
