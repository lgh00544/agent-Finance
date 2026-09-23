# PaperTradingPanel·模拟持仓 Tab 卡片化 + 关键信息突出_执行指令

## 目标
`web/src/components/PaperTradingPanel.tsx` 模拟持仓（"模拟持仓（3）" Tab）当前用 Table 把字段摊成细长列，展开行又重复塞入风控计划/行情事实/监控研判/K线，导致：
- 页面纵向被推得很长
- 当前价、浮动盈亏不突出
- 字段多但信息层次不清

改为**卡片网格 + Drawer 详情**。

## 改动点

### 1. 列表形式改造（line 250-251 positions Tab）
将 Table 替换为响应式卡片网格：
```
<Row gutter={[12, 12]}>
  {positions.map((pos) => (
    <Col xs={24} md={12} xl={8} key={pos.id}>
      <PositionCard pos={pos} onKline={setKlinePosition} onDetail={setDetailPosition} />
    </Col>
  ))}
</Row>
```
- 空态保留："暂无模拟持仓"
- loading 态：用 `Card loading` 网格占位（或原 `summaryQuery.isLoading`）

### 2. 新增 `PositionCard` 组件（文件内函数，≤ 80 行）
每张卡结构：
- **顶部主区**：
  - `stock_code` + `name`（`Text strong` 16px）
  - 现价 `current_price`：大号 `Title level={3}` 或 Statistic（`valuationMoney`）
  - 涨跌幅：取 `change_pct` 或从 `current_price/avg_price` 估算；A 股涨红跌绿（盈利/上涨红 `#ef4444`，亏损/下跌绿 `#10b981`）
  - 浮动盈亏 `pnl_pct/pnl_amount`：Tag 颜色同上
- **中部摘要条**（Space wrap）：
  - 持仓 / 可卖
  - 成本价
  - 市值
  - 生命周期阶段（`phaseLabel(lifecycle.phase)`）
  - 行情来源/状态（Tag）
  - 建仓日期
- **底部操作**：
  - Button「K线」→ `onKline(pos)`
  - Button「详情」→ `onDetail(pos)`
- Card 高度固定或最小高度，避免被内容撑爆；body 内内容用 `Space direction="vertical"` 间距 12

### 3. Drawer 扩展为「持仓详情」（复用现有 K 线 Drawer）
现有 Drawer（line 365-382）只放 K 线图。改为：
- Drawer 标题：`{code} {name}`
- 顶部一行 4 个 Statistic：现价 / 浮动盈亏 / 持仓 / 市值
- Tab 或 Space 分块：
  - **风控计划**：调用已有 `controlDetails(pos)`
  - **行情事实**：来源/状态/行情时间/事实时间/参考行情提示
  - **监控研判**：`pos.metadata?.monitor`
  - **卖出决策**：`pos.metadata?.sell_decision`
  - **K线图**：现有 `<KlineChart ... />`
- 新增 state `const [detailPosition, setDetailPosition] = useState<PaperPosition | null>(null)`
- Drawer 宽度 720px，`destroyOnHidden`

### 4. K 线按钮与详情按钮可并存
- 点击「K线」直接打开 Drawer 并滚动到底部/定位到 K 线 Tab（或用 Segmented 切到"K线"）
- 点击「详情」打开 Drawer 默认显示"风控计划"Tab

### 5. 删除原 Table 的 expandable
卡片自身不内联展开；所有长内容进 Drawer。避免页面被推高。

## 红线
1. **不动后端/API/queryFn**，不动模拟账户创建/运行/暂停/补跑/归档逻辑
2. **不动其他 4 个 Tab**（模拟流水/研究上下文/联网证据/模拟告警）
3. 所有原字段必须在 Card 或 Drawer 中可见，**不丢信息**
4. A 股颜色约定：涨/盈 → 红 `#ef4444`；跌/亏 → 绿 `#10b981`
5. `KlineChart` 调用方式不变；`opened_trade_date` 缺失时仍传 `''`（由 KlineChart 自身 disabled）
6. 改动 ≤ 130 行，不新增独立组件文件

## 验证
1. 模拟持仓页显示为卡片网格（大屏 3 列、中屏 2 列、小屏 1 列）
2. 每张卡顶部一眼看到：代码/名称、现价、涨跌幅 Tag（红/绿）、浮动盈亏 Tag（红/绿）
3. 卡中摘要条有：持仓/可卖、成本、市值、生命周期阶段、行情状态、建仓日期
4. 点击「详情」打开 720px Drawer，可见风控计划/行情事实/监控研判/卖出决策/K线 5 块
5. 点击「K线」打开同一 Drawer 并定位到 K 线块
6. 页面不再因单票风控计划长文本而被纵向撑高
7. 空态/加载态/颜色约定/响应式均正常
