# PaperTradingPanel·模拟持仓行加 K 线图入口_执行指令

## 目标
sir 实测：模拟持仓（指数页·AI 模拟账户·"模拟持仓" Tab）的持仓行要加一个入口，直接看对应票的 K 线图，不需要再去其他软件翻图。

## 前提
- `web/src/components/charts/KlineChart.tsx` 已存在，props：`code/name/anchorDate/anchorKind/days/height`
- 后端 `GET /kline/{code}?start&end` 已就绪
- 模拟持仓字段：`PaperPosition.stock_code: string`、`name?: string`、`opened_trade_date?: string`

## 改动点

### 1. 导入（line 1-14）
- line 2-5 antd import 加入 `Drawer`
- line 14 import 中加入 `KlineChart`（从 `@/components/charts/KlineChart`）

### 2. State（line 175 后）
新增：
```
const [klinePosition, setKlinePosition] = useState<PaperPosition | null>(null)
```

### 3. positionColumns 新增"操作"列（line 186 后/最后一个列前）
在"建仓日期"列之前或最后追加一列：
```
{ title: 'K线', width: 80, render: (_: unknown, row: PaperPosition) => (
  <Button size="small" type="link" onClick={() => setKlinePosition(row)}>K线</Button>
)} }
```
同时给现有列补 width，避免新增列后 Table 列宽自动压缩：
- line 180 "标的" → width 120
- line 181 "持仓 / 可卖" → width 120
- line 182 "成本价" → width 100
- line 183 "现价 / 市值" → width 120
- line 184 "浮动盈亏" → width 130
- line 185 "行情来源 / 状态" → width 180
- line 186 "建仓日期" → width 110
- line 251 positions Table `scroll={{ x: 980 }}` → 改为 1100（预留操作列 + K 线按钮）

### 4. K 线 Drawer（Tabs 结构 line 250-260 之后）
在 `</Card>` 闭合之前加入：
```
<Drawer
  title={klinePosition?.stock_code ? `${klinePosition.stock_code} ${klinePosition.name ?? ''} K线` : 'K线'}
  open={!!klinePosition}
  onClose={() => setKlinePosition(null)}
  width={720}
  destroyOnHidden
>
  {klinePosition ? (
    <KlineChart
      code={klinePosition.stock_code}
      name={klinePosition.name}
      anchorDate={klinePosition.opened_trade_date ?? ''}
      anchorKind="entry"
      days={60}
      height={360}
    />
  ) : null}
</Drawer>
```

### 5. （可选）expandable 行内也追加 K 线
line 251 positions Table 的 `expandable.expandedRowRender` 当前返回 `<FactDetails value={{...}} />`。在其后追加 K 线图：
```
const pos = row as PaperPosition
return (
  <Space direction="vertical" size={16} style={{ width: '100%' }}>
    <FactDetails value={{ '事实时点': pos.fact_as_of, '监控研判': pos.metadata?.monitor, '卖出决策': pos.metadata?.sell_decision }} />
    <KlineChart code={pos.stock_code} name={pos.name} anchorDate={pos.opened_trade_date ?? ''} anchorKind="entry" days={60} height={280} />
  </Space>
)
```
**注意**：expandable 内部 already 是 row 渲染上下文，需把 `row` as PaperPosition 后使用。由于原 render 已用 `row.fact_as_of/row.metadata`，类型可直接断言。

## 红线
1. **不动后端、不动 API、不动 queryFn**
2. **不动模拟账户创建/运行/暂停/补跑逻辑**
3. **不动 executions/contexts/evidence/alerts 4 个 Tab**
4. K 线只读展示，**不写**任何交易/监控逻辑
5. `opened_trade_date` 缺失时 anchorDate 传空字符串；KlineChart 内部会处理为无锚定竖线（不要伪造日期）
6. 改动 ≤ 50 行，不新增文件

## 验收
1. 模拟持仓 Tab 每行出现"K线"按钮
2. 点击按钮弹出 720px Drawer，标题为 `{code} {name} K线`
3. Drawer 内显示 60 日 K 线蜡烛图，A 股涨红跌绿，含成交量、MA5/10/20
4. 建仓日（opened_trade_date）出现黄色竖线；若缺失则无竖线
5. 展开行（+ 号）也在下方出现同一只票的 K 线图
6. 关闭 Drawer 后再点其他票，K 线重新加载；Drawer 外其他功能未受影响
