# 行业消息雷达批 1 MVP 执行指令——修订版

> **关联方案**：`D:\self\行业消息面Agent_MVP_方案_修订版.md`
> **执行者**：Claude Code / DSH
> **决策人**：sir
> **工作目录**：`D:\self`

## §一 目标

完成一个**观察型消息雷达**：

`抓取 -> 标准化 -> 去重 -> 行业映射 -> AI 解读 -> K228 校验 -> React 展示 -> shadow 记录`

本批不创建 LangGraph Agent，不接 Discover/Score/Monitor，不改变候选池，不自动修改行业字典。

## §二 开工前必须确认

1. 数据源是否包含真正的政策/行业来源；
2. 若暂时只有 `fetch_news`，所有结果标记 `source_scope=company_signal`；
3. 行业代码、行业名称、别名和实体映射是否已有人工确认版本；
4. 数据库迁移方式和现有表兼容方式；
5. shadow 统计的 T+1/T+3/T+5 字段和样本口径。

任一项未确认，停在报告，不自行假设。

## §三 实现边界

允许修改：

- `backend/app/db/models.py` 或现有迁移入口；
- 新增消息雷达 service/repo/API；
- 新增最小测试；
- `web/src/pages/NewsSectorPage.tsx`、API 客户端和菜单入口。

禁止修改：

- `backend/app/graph/*`；
- `backend/app/agents/discover.py`、`score.py`、`monitor.py`；
- `agent_prompts/*`；
- `tradeable_view`、交易规则、评分权重；
- 现有 `news_article` 写入逻辑；
- Streamlit 页面。

## §四 必备字段和状态

原文必须保留：

- `source_type`、`source_name`、`source_url`；
- `external_id` 或 `content_hash`；
- `published_at`、`fetched_at`；
- `sector_codes`、`mapping_method`、`mapping_confidence`；
- `status`：accepted/unmapped/human_review/rejected/expired。

AI 解读必须保留：

- `polarity`；
- `impact_mechanism`；
- `impact_horizon`；
- `information_score`；
- `direction_confidence`；
- `quote_evidence`，含 article_id、原文片段、起止位置；
- `affected_stock_codes`；
- `stock_relation_basis`；
- `human_review_required`；
- `validator_status`；
- `model_version`。

## §五 K228 校验

独立函数实现，至少覆盖：

1. article ID 存在；
2. quote 是原文标准化文本的精确子串；
3. quote 保存位置；
4. 来源、URL、时间字段完整；
5. 禁止买卖、目标价、仓位和推荐性表达；
6. 无原文依据的具体股票关联直接人工复核；
7. 内容冲突时输出 mixed/uncertain；
8. 校验失败不得进入正式展示结果。

禁止使用“建议出现两次才熔断”或“超过 50% 字符”作为唯一校验。

## §六 页面要求

页面命名为“行业消息雷达”，每行显示：

- 来源与发布时间；
- 行业归属与置信度；
- 利好/利空/中性/不确定；
- 影响机制；
- 原文引用；
- 是否成分股新闻代理信号；
- 是否待人工复核。

页面顶部显示实验性提示，不把“高信息量”显示成“确定利好”。

## §七 测试与验收

最小测试必须覆盖：

1. 同 external_id/content_hash 幂等；
2. 映射失败进入 unmapped；
3. 多行业映射不强行覆盖；
4. quote 精确匹配通过；
5. quote 不匹配拒绝；
6. 推荐性表达触发 human_review；
7. 无来源或异常时间不生成正式解读；
8. 用户反馈不直接修改字典；
9. MVP 不调用正式 Agent prompt。

测试只跑本批相关文件。不得以“全量 pytest 全绿”替代上述验收。

## §八 停止条件

遇到以下任一情况立即停下报告 sir：

- 需要新增 LangGraph 节点；
- 需要改交易规则、评分权重或正式 prompt；
- 需要让 LLM 修改行业字典；
- 需要把成分股代理信号宣称为行业新闻；
- 需要删除原始证据才能通过测试；
- 业务实现超出当前批准范围。
