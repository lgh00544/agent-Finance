# 工单7 HotMoneyPage 补全

## 目标
补齐 HotMoneyPage 相对旧版 5_游资追踪.py 缺失的 4 块：档案 tier 筛选 + 详情、流水按日/代码筛选 + 命中游资 + 日汇总、席位监控、研判留痕（跨模块联查）。**仅改 HotMoneyPage.tsx 单文件**，后端/API/类型零改动（接口已实存：hotMoneyProfiles 带 tier、hotMoneyFlows 带 date/code、hotMoneyTraces、通用 traces）。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| Profiles 组件 | 加 tier 下拉筛选（一线/二线/观察），queryKey 带 tier，调用升级为 `hotMoneyProfiles(q, tier)` | 复用已有 tier 参数 |
| Profiles 行 | 加「展开详情」：协同席位 co_seats / 擅长题材 good_themes / 5日胜率 last_review_at / source | 用 Table expandable |
| Flows 组件 | 顶部加 date Select（从 rows 去重 trade_date）+ code 输入，调用 `hotMoneyFlows(date, code)`；空态提示 | 复用 API date/code |
| Flows 表格 | 新增列：命中游资（seat_name 匹配 actor_name）/ 置信度 confidence / 上榜原因 disclosure_reason | 纯展示 |
| Flows 汇总 | 顶部 3 stat（流水条数 / 净买入合计 / 净卖出合计，moneyCn）| 红涨绿跌 |
| 新增「席位监控」tab | 选游资 → seats={seat_code}+co_seats → 从 flows 过滤 → 最近操作列表（净买方向 stat + 明细）| 复用现有数据，无新接口 |
| 新增「研判留痕」tab | `hotMoneyTraces(code)` 列表 + 「跨模块联查」展开调用 `traces(code)` 排除自身 | 复用已有热钱留痕 + 通用 traces |

## 红线

1. 只改 `web/src/pages/HotMoneyPage.tsx`；禁止动 backend / api/hotMoney.ts / types
2. 不新增依赖（仅用已有 antd：Select/Statistic/Card/Tag/Space/Table）
3. 复用已有 moneyCn / StockLabel / EmptyState / ErrorCard；悬停不使用新组件
4. 不触发任何 LLM / 后台任务，纯读缓存数据
5. 空数据一律显示「—」或 EmptyState，不编造

## 验收清单

- [ ] 4 tab 齐全：档案(带展开+tier筛选) / 流水(带日+代码筛选+命中+汇总) / 席位监控 / 研判留痕(联查)
- [ ] tsc -b + npm build 0 error；oxlint 0 error
- [ ] 红涨绿跌、空态、悬停均符合项目风格
- [ ] 灰度单文件提交为 `feat(hotmoney): 页面补全 - tier筛选/流水汇总/席位监控/研判留痕`

## 参考
- 旧版：D:\self\streamlit\pages\5_游资追踪.py（fold_module hm_seat / hm_trace 语义）
- 类型：web/src/types/index.ts:336-363（HotMoneyProfile / HotMoneyFlow / 通用 Record<string,unknown>）
- 通用联查：web/src/api/traces.ts（`traces(code, date?)`）