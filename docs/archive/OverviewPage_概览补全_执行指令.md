# OverviewPage 概览补全（市况速览 + 持仓红线分类）

## 目标
`web/src/pages/OverviewPage.tsx` 工作区有一份 +147/-58 未提交改动（市况速览/持仓红线分类/可建仓优先）。作为独立工单验收、补缺口、单独提交。

## 现状（工作区改动已实现，先 `git diff HEAD -- web/src/pages/OverviewPage.tsx` 通读）

已实现：
- **市况速览**：三大指数卡（marketIndices）+ 严格度 tag（marketCondition 的 strictness）；A股红=强/绿=弱（bandColor/strictColor 已映射）
- **持仓红线分类卡**：从 holdingQuotes 按现价 vs 止盈/止损、redLineCheck 命中（c1/c2/c3/c4/K226/K189）分 4 类卡（红线预警/止盈/止损/正常）
- **可建仓优先**：candidate_tradeable items 里 is_tradeable 前置展示

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| OverviewPage.tsx 全程 | 校验补全改动：编译、接口实存、样式变量、China 涨红/跌绿 | 接口已核实实存（marketIndices/marketCondition/redLineCheck），勿新建 |
| 红线分类卡 | 确认 4 类卡渲染完整、空态/无数据兜底、5 分钟轮询不炸 | 保留既有取数逻辑 |

## 红线
1. 只改 `web/src/pages/OverviewPage.tsx`；禁动后端 / API / 其它页面 / types
2. 不新增依赖、不改接口签名；复用既有 query 与 api
3. 颜色 China 语义：强/涨=红(var--up)、弱/跌=绿(var--down)

## 验收清单（≤6）
- [ ] `npx tsc --noEmit` 0 error + `npx oxlint` 0 error + `npm run build` EXIT=0
- [ ] 市况速览：三大指数 + 严格度 tag 渲染，band/strict 色映射符合 China 语义
- [ ] 持仓红线分类：止盈/止损/红线/正常 4 类卡数据正确，redReason 中文明确（C1集中/C2回撤/C3止损/C4突破/K226/K189）
- [ ] 空态/无数据不渲染或显「—」，5min 轮询不炸
- [ ] 后端/接口/类型零改动，仅 OverviewPage.tsx 一个文件
- [ ] `git add web/src/pages/OverviewPage.tsx && git commit -m "feat(overview): 市况速览 + 持仓红线分类 + 可建仓优先"`（只 add 此文件）