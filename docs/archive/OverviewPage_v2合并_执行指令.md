# OverviewPage 优化（3 件事合并）

## 目标

`D:\self\web\src\pages\OverviewPage.tsx` 单文件改：① 「今日候选」stat card 改真实数据；② 新增持仓概览卡；③ 复用 holdingQuotes 缓存。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| import 区 | 新增 `import { holdingQuotes } from '@/api/holdings'` | 已在 HoldingsPage 用过 |
| dashboard useQuery 附近 | 新增 `useQuery({queryKey:['holding-quotes-overview'], queryFn:holdingQuotes, refetchInterval:60_000})` | 60s 缓存复用 |
| L104 candidates 解构后 | 新增 `const tradeable = mods.candidate_tradeable ?? {}` | 真实当日可建仓数 |
| L122 stat card #1 | `label:"今日可建仓"` / `value:tradeable.count` / `sub:${date} · 候选池 ${total} 只` / count=0 时 tone 改 warn | 与 CandidatesPage 同源 |
| L138「移动止盈计划」下方 | 新增「当前持仓概览」卡：grid auto-fill 280px，每只持仓一卡展示 9 项（代码/名称/涨幅Tag/持股/成本/现价/市值/浮盈/止损/止盈），底部标注 quote_time 与刷新机制 | 不触发 LLM、不调 useTaskSubmit |

## 红线

1. 不动后端 / API 层 / 类型定义（holdingQuotes 已存在）
2. 不引入新依赖
3. 不触发 LLM 分析（所有字段都是 holdingQuotes 原始数据）
4. 不动「最新评分」卡（L160-168）
5. 不删 candidates 解构（保留供未来用）
6. 不弹 toast / modal / 跳转
7. 空持仓时「当前持仓概览」卡不渲染
8. 涨红跌绿（A 股惯例）
9. 行情涨（pnl>0）Tag color=red，跌 Tag color=green

## 验收清单

- [ ] tsc --noEmit 0 error
- [ ] oxlint src/pages/OverviewPage.tsx 0 error
- [ ] stat card #1 label="今日可建仓"，value=tradeable.count，sub 含日期
- [ ] 切 CandidatesPage 同日，「可建仓」Tag 数 = stat card value
- [ ] count=0 时 stat card tone 变 warn
- [ ] 「当前持仓概览」卡出现在「移动止盈计划」下方
- [ ] 每只持仓一卡展示 9 项 + 涨红跌绿
- [ ] 卡底显示 quote_time + 「监控定时 5 分钟轮询」说明
- [ ] 不触发新 LLM（Network 面板 holdingQuotes 只调 1 次）
- [ ] 空持仓时卡片不渲染
