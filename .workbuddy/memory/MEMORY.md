# D:\self 项目滚动归档（主题分类）

> **写于**：2026-08-20，整理自 2026-08-13 ~ 2026-08-20 daily logs
> **目的**：daily log 散落信息按主题压缩存档；项目使命/批次进度/红线等长期事实见 `PROJECT_STATE.md`
> **限制**：本文件作为机器快查索引，保留所有长期铁律；字符上限不再硬性约束 3000（旧规范已不适用，新规则加入后内容必要）。

## 协作模式（永久生效）

- sir 提需求 → Lark **直接出 Claude Code 提示词**（2026-08-19 起永久生效），仅需求+规则+约束，不含代码。**sir 不用每次都说"给我让 Claude Code 执行的提示词"**——这是默认。
- 唯一例外：涉及交易规则/研判标准/红线时，提示词内加"红线约束"段。
- 大型需求（5+ 批次/多模块联动）→ 先出方案文档（`D:\self\{主题}_方案.md`）→ 再出多批次执行指令（`D:\self\{主题}_{N}批次_Claude执行指令.md`）。
- 多批次执行指令结构：每批次包含 0 元信息 + 一目标 + 二架构约束 + 三规则 + 四实现参考 + 五执行顺序 + 六验证清单 + 七红线。批次按依赖排顺序。
- 审核任务交付（2026-08-17）：必须给"可复制给其他 agent 的总结段"，含 ①问题②操作③文件路径。
- 工程师交接（2026-08-17）：自然语言 5 要素——文件在哪/做什么/为什么/预期/思考。

### 🔴 前端默认改新版 React，不动 Streamlit（2026-08-20 sir 拍板，永久生效）

所有"页面/交互/组件/UI 文案/排序/筛选/徽章/Tab"修改 → **默认只改 `web/src/`**。Streamlit（`streamlit/pages/`）只在三种情况动：①后端 API 变更导致旧版报错阻塞使用 ②sir 显式点名 ③React 侧功能尚未迁移（查工单列表）。歧义 → 先问 sir，不擅自决定。

**不受此规则影响**：后端/数据/Agent/交易规则/研判标准——只动后端，两端都消费。

**已固化**：4400% 修复、复盘徽章排序、TaskDrawer 升级等按 React 新版出。Streamlit 同名指令保留可回滚，优先级**永远低于** React 版。

## 设计哲学（sir 拍板）

- LLM 输出"艺术判断" → 代码层换算"可执行事实"（100 股整数倍、股数、金额）
- 展示层永远给最终可执行数字，不给中间值
- 边界自动处理、每个节点有人工控制入口
- 功能不成熟不展示，不制造噪音

## 高频陷阱（执行/审核必查）

1. `structured.py:32` 注释"LIGHT=Discover 初筛"是**错的**，Discover 3 处全 DEEP
2. `fetch_industry_spot` 需传 `kind="snapshot"` 才走断路器
3. dashboard 聚合**禁止**调 `tradeable_view()`（ensure_if_missing 触发 900 次 DB 查询），用 `repo.list_candidate_tradeable(trade_date, limit=50)`
4. `repo.list_candidate_tradeable` 字段是 `tier/price_zone/label/block_reason`（**不是** `grade/reason/potential_flag`）
4a. 复盘追踪列表缺徽章/排序：Streamlit `D:\self\选股效果验证_排序加徽章_执行指令.md` + React `D:\self\React复盘页徽章排序_执行指令.md`（均未执行）
4b. **React 候选池页默认拉全表 bug**（2026-08-20）：`CandidatesPage.tsx:480` 的 `date` state 始终 undefined，`<Select value={date ?? dates?.[0]}>` 是非受控显示，queryFn 实际传 undefined → repo 拉全表 39 条。**修复模板**：`useEffect(() => { if (!date && dates?.length) setDate(dates[0]) }, [dates, date])` + `enabled: !!date`。指令：`D:\self\React候选池页默认仅最近一次生成_执行指令.md`
4c. **同 trade_date 下所有候选共用同批生成时间**（毫秒级差），"最近一次生成结果"=trade_date 最大的那一天全部候选
5. `TradeProfile` 在 `web/src/types/index.ts:294`（**不是** `types/trade.ts`——该文件不存在）
6. win_rate 口径：`track_verify._group_stats` 0-100 百分制；`_calc_stats` 0-1 小数——展示层必须显式归一化（防 4400%）。**React 新前端 `CandidatesPage.tsx:572` 和 `ReviewsPage.tsx:132` 曾误把百分制再乘 100，已出修复指令 `D:\self\React前端胜率展示修复_执行指令.md`**
7. `WebFetch` 失效时用 `request` 直调 akshare：market_hours.snapshot_allowed() 是交易日闸门
8. `useEffect` 替代写法是死循环——不要在 render 阶段直接 `form.setFieldsValue`
9. tsc EXIT=0 零错不代表落地——未使用 import/函数 tsc 不报警，必须 `grep 关键标识 | wc -l` 核对
10. AppTest 22 failed 是**环境性内存压力**，与代码无关

## 关键术语映射

- "批次" = 一次完整开发周期（Claude Code 提示词 + 实施 + 验收）
- "工单" = React SPA 补全的 v1→v2 子任务（工单 1-6 已完成，工单 7-12 进行中）
- "auto-merge" = GitLab 自动合入的 PR——**永不**改交易规则/研判标准表
- "review_log" = 所有规则改动的可回滚审计

## 调试快速路径

- 数据不显示 → `curl /api/<endpoint>` 直验后端；浏览器 vs 后端分离判定
- LLM 异常 → 先 `light_stats` / `deep_stats` 看命中率，3 次失败自动降级
- 任务调度 → `job_status()` 接口看 `last_*` 时间戳
- 行情缺失 → `sector_snapshot.updated_at` + `sector_refresh_job` cron 日志
