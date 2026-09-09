# K 线图共享组件 + 三页接入（A 股约定·60 日）_执行指令

## 目标
sir 需求：候选池/持仓监控/复盘页都能直接看 K 线（不外跳软件）。现有 `GET /kline/{code}?start&end` 已就绪但仅在复盘用 line 渲染——新增一个**共享 K 线图组件**，三页统一接入，**A股涨红跌绿**色约定，**默认前后 60 日**。

## 架构约束
- **新建** `web/src/components/charts/KlineChart.tsx`：单个可复用组件，封装 echarts candlestick + 成交量柱状 + 标记线（建仓日/选中日/离场日）
- 三页**只调用组件，不重写 option**：CandidatesPage / HoldingsPage / ReviewsPage
- 体积/颜色/数据全在组件内计算，调用方只传 `{ code, name, anchorDate, days, anchorKind }`
- 不动后端、不加 API
- 范围内 `web/src/components/charts/ChartCard.tsx` 不改（仍可作外层卡，KlineChart 内部自含 Card）

## 规则

### KlineChart 组件签名
```
<KlineChart
  code="000001"            // 必填
  name="平安银行"           // 可选，仅用于标题
  anchorDate="2026-09-03"  // 可选，触发那天的竖线
  anchorKind="select"      // select/entry/exit/now → 不同颜色竖线
  days={60}                // 默认 60
  height={320}             // 默认 320
/>
```

### 颜色约定（A 股涨红跌绿）
- 涨：`#ef4444`（red）填充
- 跌：`#10b981`（green）填充
- MA5/10/20：白/黄/紫细线
- 锚定竖线：建仓日黄 `#eab308`、选中日蓝 `#3b82f6`、离场日红 `#ef4444`、今天绿 `#10b981`
- 量柱同涨/跌色

### 数据获取与失败态
- 调 `GET /kline/{code}?start={anchor-30d}&end={anchor+30d}`（KlineChart 内部 useQuery）
- 缺数据 → `EmptyState text="该股 K 线缺失，请检查是否在交易时段外或后端接口"`（**禁止** 0 或占位）
- 失败/404 → `ErrorCard` + 重试
- 加载中 → Skeleton 6 行

### 标的上下文（标题上方）
- 卡片 title 行：`{code} {name} K线 · {anchorDate} ±{days}日`
- title 右上角 extra：锚定日 `Tag`：选中日（蓝）/ 建仓日（黄）/ 离场日（红）

## 三页接入
| 页 | 接入点 | 传入参数 |
|---|---|---|
| `CandidatesPage.tsx` | 现有"详情/历史"抽屉（line 274-293 closeDetail 附近）新增一个 Tab "K线"或追加到顶部 ChartCard | `code=c.stock_code, name=nameOf(c), anchorDate=c.trade_date, anchorKind='select'` |
| `HoldingsPage.tsx` | 现有 HoldingDrawer（line 458-504）追加 ChartCard 段 | `code=h.stock_code, name=h.stock_name, anchorDate=h.entry_date, anchorKind='entry'` |
| `ReviewsPage.tsx` | ReviewDrawer 内 line 302-324 把现有"多日盈亏曲线 line 图"**替换**为 KlineChart | `code=r.stock_code, name=r.stock_name, anchorDate=r.exit_date, anchorKind='exit'` |

## 红线
1. **不动后端**：包括 `/kline` 接口契约、参数、返回结构
2. **不重写 echarts 6** 已有逻辑；只新增 `KlineChart.tsx` 一个文件
3. 不改后端 schemas、API 路径
4. 不动 echarts 6 系列类型：candlestick + bar（成交量） + line（MA） + markLine（锚定）
5. 三页接入**仅做"插入组件 + 传参"**，不动其他渲染逻辑
6. 改动 ≤ 150 行（含 3 页接入）；KlineChart 内部 ≤ 120 行；不写测试

## 验证
1. 进每日候选池 → 任一候选行点开 → 抽屉内出现 K 线蜡烛图（红涨绿跌）、60 日范围、选中日蓝色竖线
2. 进持仓监控 → 任一持仓"详情/操作" → Drawer 末尾出现 K 线图，建仓日黄色竖线
3. 进交易复盘 → 任一条目 → 抽屉内原本"多日盈亏曲线"已被 K 线图替换，离场日红色竖线
4. 停盘日/数据缺失时显示 EmptyState，不渲染假图
5. 加载中 Skeleton；网络错误 ErrorCard 可重试
6. 蜡烛颜色：涨红跌绿（A股约定）；MA 5/10/20 细线
