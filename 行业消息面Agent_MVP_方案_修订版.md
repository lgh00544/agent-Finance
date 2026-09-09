# 行业消息面模块（News Radar）MVP 方案——修订版

> **修订目的**：在保留原方案“先不上 LangGraph 新 Agent、先做 MVP”的优点基础上，修正数据定义、需求边界、治理闭环和验证指标。
>
> **当前定位**：行业消息观察工具 + shadow 验证底座，不是正式 Agent，不直接改变候选池排序，不产生买卖建议。
>
> **决策人**：sir
> **日期**：2026-09-07

## 一、先说清楚要解决什么

用户真正需要的是：

1. 周末、隔夜和盘前不漏掉重要消息；
2. 知道消息原文、来源、发布时间和涉及行业；
3. AI 判断消息属于利好、利空、中性还是不确定，并说明影响机制；
4. 在证据充分时，给出“可能涉及的标的范围”，但不直接推荐买卖；
5. 经过真实数据验证后，判断它能否成为候选池的一个弱特征。

因此本项目分三层推进：

| 层级 | MVP 是否做 | 作用 |
|---|---:|---|
| 消息雷达 | 是 | 抓取、去重、行业归属、证据化展示 |
| 行业影响解读 | 是 | 利好/利空/中性/不确定 + 影响机制 |
| 标的关联与候选池特征 | 仅做影子记录 | 不进入正式排序，验证后再决定 |

**MVP 不宣称已经具备行业到个股的预测能力。**

## 二、架构决策

### 2.1 不新增 LangGraph Agent

本阶段采用独立 service + API + React 页面：

```text
数据源适配器
    -> 原文标准化/去重
    -> 行业映射
    -> AI 结构化解读
    -> K228 校验
    -> 只读页面 + shadow 结果
```

不接 Discover、Score、Monitor 的正式 prompt，不改变候选池，不修改交易规则。

### 2.2 明确数据源口径

现有 `fetch_news` 是个股新闻/公告接口。使用它时，数据必须标记为：

> `source_scope=company_signal`：成分股新闻代理信号

不能把它包装成完整的行业新闻。

真正的行业政策、监管、产业链、海外事件应通过独立数据源适配器接入，并记录：

- `source_type`：官方政策 / 行业媒体 / 公司公告 / 市场媒体；
- `source_name`；
- `source_url`；
- `published_at`；
- `fetched_at`；
- `external_id` 或 `content_hash`。

若 MVP 暂时只有成分股新闻，页面必须显示“成分股新闻代理信号，行业覆盖不完整”。

### 2.3 行业映射规则

`sector_dict_v1` 只允许人工维护，不允许 LLM 修改。字典至少区分：

- 行业代码与标准名称；
- 行业别名；
- 公司实体别名；
- 产品/政策关键词；
- 映射方法：`exact_entity`、`exact_keyword`、`source_tag`、`unmapped`；
- 映射置信度；
- 字典版本和审核人。

规则：

1. 直接命中标准行业或明确实体，可进入候选映射；
2. 只命中模糊词的新闻进入 `unmapped` 或 `human_review`；
3. 同一新闻命中多个行业时保留多映射，不强行选唯一行业；
4. “最多取 5 只成分股”只能作为成本限制，不能作为行业覆盖率证明；
5. 不使用头部成分股样本推断整个行业已经被覆盖。

## 三、数据模型

不强行限制为三张表。审计字段比表数量更重要。建议新增四类数据：

### 3.1 `sector_news_article`

保存标准化原文和映射结果：

`id / source_scope / source_type / source_name / external_id / title / content / source_url / published_at / fetched_at / content_hash / sector_codes / stock_codes / mapping_method / mapping_confidence / status / created_at`

`status` 至少支持：

`accepted / unmapped / human_review / rejected / expired`

不得仅依赖 24 小时物理删除。过期内容应保留最小审计记录，正文可按存储策略归档。

### 3.2 `sector_news_ai_interpret`

保存一次解读：

`id / article_ids / sector_codes / polarity / summary / impact_mechanism / impact_horizon / information_score / direction_confidence / quote_evidence / affected_stock_codes / stock_relation_basis / human_review_required / validator_status / model_version / created_at`

重要定义：

- `information_score` 表示证据完整度，不表示涨跌确定性；
- `polarity` 取 `positive / negative / neutral / mixed / uncertain`；
- `affected_stock_codes` 只记录原文明确涉及或字典高置信关联的代码；
- `stock_relation_basis` 必须说明是“原文明确提及”还是“行业映射关联”；
- 不生成目标价、买卖建议、仓位建议。

### 3.3 `sector_news_feedback`

用户点击“无效”只产生反馈记录：

`article_id / interpret_id / feedback_type / reason / reviewer / status / created_at`

反馈不得直接修改字典。字典 v2 必须经过人工审核、版本化和可回滚。

### 3.4 `sector_dict_v1`

增加：

`version / effective_from / effective_to / reviewed_by / review_status`

不得让 LLM、cron 或前端操作直接改变生效字典。

## 四、K228 修订版

K228 在 sir 审批并登记前，只作为本模块的候选硬约束，不得宣称已经成为全局正式规则。

### 4.1 必须通过的校验

1. 每个 `quote_evidence` 必须对应已入库文章 ID；
2. quote 必须是原文标准化后的精确子串，并保存起止位置；
3. 原文必须有来源、URL、发布时间和抓取时间；
4. AI 输出必须通过结构化 schema 校验；
5. 原文冲突时输出 `mixed` 或 `uncertain`，不得强行判定；
6. 文章重复时按 `external_id` 或 `content_hash` 幂等；
7. 来源抓取失败、发布时间异常或内容为空时，不生成正式解读。

### 4.2 越权处理

下列任一情况直接标记 `human_review_required=true`，不得进入正式候选池：

- 买入、卖出、目标价、目标位、仓位、止盈止损等建议；
- “利好某只股票”“首选标的”“值得布局”等推荐性表达；
- 具体股票关联没有原文依据；
- quote 与原文不一致；
- 把单一公司事件表述为整个行业确定性事件；
- 使用无法追溯的外部事实。

不使用“出现两次才熔断”或“超过 50% 字符”这类脆弱阈值作为唯一防线。

## 五、三道闸修订版

| 闸 | 规则 |
|---|---|
| 数据闸 | 来源、时间、URL、内容非空、去重通过；映射失败进入 unmapped |
| 证据闸 | quote 精确匹配、article ID 存在、来源可追溯；失败不入正式解读 |
| 治理闸 | 用户反馈只进入待审核队列；MVP 结果只读，不进入正式 Agent prompt |

LLM 的 `information_score` 只能作为页面排序辅助，不能单独决定“有价值”。

## 六、页面与用户体验

页面名称：**行业消息雷达**。

每条消息至少展示：

- 来源、发布时间、抓取时间；
- 行业归属及映射置信度；
- 利好/利空/中性/不确定；
- 影响机制和时间范围；
- 原文证据；
- 是否为“成分股新闻代理信号”；
- 是否需要人工复核。

“高信息量”不得显示为“已确认的实质影响”。建议使用中性标签：

- 证据完整；
- 信息一般；
- 证据不足；
- 待人工复核。

页面顶部固定显示：

> 实验性消息雷达：只提供证据化信息整理，不直接作为买卖依据，不改变候选池。

## 七、shadow 验证方案

至少连续运行 3-4 周，但必须记录可量化结果：

### 7.1 数据质量

- 有效来源率；
- 有发布时间和 URL 的比例；
- 重复率；
- 行业映射覆盖率；
- 人工抽样映射准确率；
- quote 精确匹配率。

### 7.2 解读质量

- 利好/利空/中性/不确定的人审一致率；
- 幻觉率；
- 推荐性表达拦截率；
- 多来源冲突识别率。

### 7.3 对候选池的增量价值

在 shadow 中同时记录：

- 事件发生后行业 T+1、T+3、T+5 超额表现；
- 关联标的 T+1、T+5 表现；
- 加入消息特征前后的 Top-K 命中率；
- 最大回撤和误报率；
- 与现有“催化”因子的重复率。

“增益 ≥5%”必须先定义指标和样本数，不能直接作为验收标准。没有足够事件样本前，不允许把结果升级为正式评分因子。

## 八、批次建议

### 批 0：口径和样本

确定数据源、行业标准、字段 schema、人工标注样本和验收指标。

### 批 1：观察型 MVP

原文抓取、去重、映射、结构化解读、K228 校验、React 页面、shadow 记录。

不接正式 Agent，不接候选池，不自动改字典。

### 批 2：验证与标的关联

只在批 1 数据质量达标后，增加原文明确涉及标的的影子关联；仍不改变正式排序。

### 批 3：正式接入评审

根据 out-of-sample 结果决定是否以弱特征接入 Discover/Score。接入前必须有人工审核、回滚方案和对照实验。

## 九、最终立项结论

**条件通过：可以做观察型 MVP，不批准按原方案直接做“行业消息面 Agent”。**

通过条件：

1. 修正“行业新闻完全没有”的表述；
2. 明确成分股新闻只是代理信号；
3. 补齐 schema 中缺失字段和 unmapped/feedback 流程；
4. 将 K228 作为候选模块规则，经过人工审批后再登记；
5. MVP 只读、shadow，不影响候选池；
6. 用可复验指标替代 85%、5-15%、增益 ≥5% 等未经定义的数字。
