# K 线共享组件 + 三页接入（一次性完成）_执行指令

## 目标
sir 不想再外跳软件看 K 线。已有 `GET /kline/{code}?start&end`（ReviewsPage 已用），但现画的是收盘价 line 图——**一次性**实现：
1. 新建 `web/src/components/charts/KlineChart.tsx`：candlestick + 成交量 + MA5/10/20 + 锚定竖线，A 股涨红跌绿
2. 三页接入：候选池候选行抽屉、持仓详情 Drawer、复盘 Drawer（**替换**原 line 图）

## 架构约束
- **唯一新文件**：`web/src/components/charts/KlineChart.tsx`（≤ 140 行）
- 三页只调组件 + 传参，不重写 echarts option
- 不动后端、不动 ChartCard 现有封装

## 规则

### KlineChart props
```
<KlineChart
  code="000001"            // 必填
  name="平安银行"           // 可选标题用
  anchorDate="2026-09-03"  // 锚定日
  anchorKind="select"      // select/entry/exit/now
  days={60}                // 默认 60
  height={320}             // 默认 320
/>
```

### 颜色（A 股约定）
- 涨 `#ef4444` / 跌 `#10b981`
- MA5 `#e5e7eb` / MA10 `#fbbf24` / MA20 `#a78bfa`
- 锚定竖线：select 蓝 `#3b82f6` / entry 黄 `#eab308` / exit 红 `#ef4444` / now 绿 `#10b981`
- 量柱同涨/跌色

### 数据
- `useQuery` 调 `GET /kline/{code}?start={anchor-30d}&end={anchor+30d}`
- 字段：`{ date, open, high, low, close, volume }`（按后端 schema）
- 加载中 → Card 内 `Skeleton active paragraph={{rows:6}}`
- 失败 → `ErrorCard` + 重试
- 缺数据 → `EmptyState text="该股 K 线缺失，请检查是否在交易时段外或后端接口"`（**禁止**伪造/0/占位）
- 标题：`{code} {name} K线 · {anchorDate} ±{days}日`
- title 右上角 extra：`Tag` 显示锚定日 + kind 标签

## 三页接入

| 页 | 位置 | 传入 |
|---|---|---|
| `web/src/pages/CandidatesPage.tsx` | line 274-293 现有"详情/历史"抽屉内，**追加** `<KlineChart>` 段（默认放在首位，紧跟顶部摘要之后） | `code=c.stock_code, name=nameOf(c), anchorDate=c.trade_date, anchorKind='select'` |
| `web/src/pages/HoldingsPage.tsx` | HoldingDrawer (line 458-504) **追加** `<KlineChart>` 段（放在 StatCardGrid 之后、买入/卖出操作之前） | `code=h.stock_code, name=h.stock_name, anchorDate=h.entry_date, anchorKind='entry'` |
| `web/src/pages/ReviewsPage.tsx` | ReviewDrawer 内 line 302-324 **替换** line 图为 `<KlineChart>` | `code=r.stock_code, name=r.stock_name, anchorDate=r.exit_date, anchorKind='exit'` |

## 红线
1. **不动后端**：`/kline` 接口契约/参数/返回结构
2. **不重写 echarts 6**：candlestick + bar(成交量) + line(MA) + markLine 即可
3. 不写测试
4. 三页**仅插入/替换组件段**，不重写其他渲染逻辑
5. 改动 ≤ 150 行（KlineChart ≤ 140 + 三页接入 ≤ 10 行）
6. 不动工作区其他 12 个文件的 M 状态

## 验证
1. 候选池：候选行点开 → 抽屉顶部追加 K 线图（红涨绿跌蜡烛、MA5/10/20 细线、选中日蓝色竖线）
2. 持仓监控：持仓 Drawer → 末尾追加 K 线图（建仓日黄色竖线）
3. 交易复盘：复盘 Drawer → 原"多日盈亏曲线"已替换为 K 线图（离场日红色竖线）
4. 缺数据 → EmptyState（不假造）
5. 加载中 → Skeleton；网络失败 → ErrorCard 可重试
6. 蜡烛颜色按 A 股：涨红跌绿