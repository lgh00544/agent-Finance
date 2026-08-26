# ScoresPage 评分页因子增强

## 目标
`web/src/pages/ScoresPage.tsx` 工作区有一份 +142/-43 的未提交改动（六因子色条 / tab 分组 / 3 摘要卡 / 已采纳标记）。把它作为独立工单验收、补缺口、单独提交。

## 现状（工作区已有改动，先通读 `git diff HEAD -- web/src/pages/ScoresPage.tsx`）

已实现：
- `FACTOR_NAMES` 固定六因子顺序（动量/催化/估值/主线契合/资金面/基本面质量），`factorScore()` 按名 find 定位，禁 index 假设
- `FactorBar` 色条：≥7 绿(var--down) / 4-6 黄(var--warn) / <4 灰(var--text-mute)，Tooltip 显 LLM 依据（无数据/无依据兜底）
- 3 摘要卡：今日 A/B 级 + 已被采纳（`reviewRows` filter suggest_status approved/adopted）
- 底部列表改 `Tabs` 分组（tabKey today 默认），每 tab 行数角标 + 空态

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| ScoresPage.tsx 全程 | 校验补全上述改动：编译、接口实存、样式变量、禁 index 假设 | 接口/字段已核实实存，勿新建 |
| 顶部分类摘要 | 如需 grade 分类统计缺变量（sumA/sumB/sumAdopted）补齐 | 与已实现 tab 逻辑一致 |
| 底部 Table→Tabs | 确认 cols/tabs 定义完整，selRow 详情保留 | 不要丢手动打分卡 |

## 红线
1. 只改 `web/src/pages/ScoresPage.tsx`；禁动后端 / API / 其它页面 / types
2. 不新增依赖、不改接口签名、不 index 假设
3. 样式用已有 antd + CSS 变量（var--down/warn/text-mute/up），red 取 China 涨红语义

## 验收清单（≤6）
- [ ] `npx tsc --noEmit` 0 error + `npx oxlint` 0 error + `npm run build` EXIT=0
- [ ] 6 因子色块按名定位渲染，悬停显依据；score null 显示 —
- [ ] 3 摘要卡今日 A/B/已采纳计数正确（无数据 —）
- [ ] 底部 Tabs 分组 + 角标 + 空态正常；sel 详情保留
- [ ] 后端/接口零改动，仅 ScoresPage.tsx 一个文件
- [ ] `git add web/src/pages/ScoresPage.tsx && git commit -m "feat(scores): 六因子色块/已采纳标记/摘要卡/tab分组"`（只 add 此文件）