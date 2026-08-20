# OverviewPage 优化：持仓概览卡展示具体持仓信息（成本 / 现价 / 浮盈 / 持股数 / 监控状态）

## 背景

sir 反馈 OverviewPage（系统概览页）里「持仓上累计频谱」卡只显示一行（`000725 京东方A ：北玻 — / 企查 — / 普特一天`），看不到具体持仓信息（成本 / 现价 / 浮盈 / 持股数）。

经核实：截图里的卡片**实际上对应 OverviewPage 里的「移动止盈计划摘要」卡**（L138-150），sir 想要的其实是「持仓概览卡」——把当前所有有效持仓的具体信息直接展示在首页。需求要点：

1. **展示具体信息**：成本 / 现价 / 浮盈 / 持股数 / 止损止盈等关键字段
2. **不用每次点击都分析更新**：直接读已有接口的缓存数据（dashboard 接口里 `mods.holdings` 已经返回了持仓列表），不在前端触发任何 LLM 分析
3. **由定时执行或手动执行时可以看到**：手动触发「立即刷新监控」/「运行组合哨兵」后，dashboard 接口内部会刷新 holdings 列表（60s 缓存），前端读到的就是最新数据

**对齐原则**：默认以 React 新版（`web/src/pages/*.tsx`）为准，不搬 Streamlit 旧版的 streamlit-specific 行为（st.fragment / st.rerun / st.session_state）。

## 来源文件（已读）

- `D:\self\web\src\pages\OverviewPage.tsx`（当前 175 行）
  - L95：`useQuery({ queryKey: ['take-profit-plan'], queryFn: () => takeProfitPlan() })`
  - L103：`const holdings = (mods.holdings as Array<Record<string, unknown>>) ?? []` —— 已拿到 holdings 数组但只用 `holdings.length`
  - L138-150：「移动止盈计划摘要」卡片，循环 tpPlans.rows，**只显示止损 / 止盈 / 目标仓位 3 个数字**
  - L160-168：「最新评分」卡片（sir 不是指这个，无需改）
- `D:\self\backend\app\services\dashboard.py:74`：`"holdings": lambda: repo.list_holdings(status="holding")`
- `D:\self\web\src\api\holdings.ts:9`：`holdingQuotes(): Promise<HoldingQuotes>`（返回 rows，每行含 stock_code/stock_name/shares/entry_price/current_price/market_value/stop_loss/take_profit/target_pct 等字段）
- `D:\self\web\src\types\index.ts`：`Holding` 类型定义含以上字段

## 改动 1 个文件：`web\src\pages\OverviewPage.tsx`

### 改动 1 — 复用已有 `holdingQuotes` 接口获取持仓具体信息（约 6 行）

在 OverviewPage 组件内（dashboard 查询附近）新增：

```tsx
const { data: quotes } = useQuery({
  queryKey: ['holding-quotes-overview'],
  queryFn: () => holdingQuotes(),
  refetchInterval: 60_000,  // 与 HoldingsPage 保持一致
})
```

并在 import 区域新增 `import { holdingQuotes } from '@/api/holdings'`。

**为什么用 holdingQuotes 而不是 mods.holdings**：
- `mods.holdings` 是 dashboard 聚合接口返回的原始 holding 记录，没有当前行情（current_price / market_value），只有 entry_price / stop_loss 等静态字段
- `holdingQuotes` 已经聚合了行情快照（与 HoldingsPage 同源），60s 缓存命中后实时刷新
- HoldingsPage 已经用这个接口（L531-533），无需后端改动

### 改动 2 — 新增「当前持仓概览」卡（约 35 行）

**位置**：在「移动止盈计划摘要」卡片（L138-150）的**下方**插入新卡片；在「最新评分」卡片的**上方**。

```tsx
{quotes?.rows?.length ? (
  <Card size="small" title="当前持仓概览（每日定时 / 手动触发后刷新）" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
      {quotes.rows.slice(0, 12).map((q) => {
        const h = q as Record<string, unknown>
        const code = String(h.stock_code ?? '—')
        const name = String(h.stock_name ?? '')
        const shares = Number(h.shares ?? 0)
        const cost = Number(h.entry_price ?? 0)
        const price = h.current_price != null ? Number(h.current_price) : null
        const mv = h.market_value != null ? Number(h.market_value) : (price != null ? price * shares : 0)
        const pnl = (price != null && cost > 0) ? (price - cost) * shares : null
        const pnlPct = (price != null && cost > 0) ? (price - cost) / cost * 100 : null
        const sl = h.stop_loss ?? '—'
        const tp = h.take_profit ?? '—'
        const pnlColor = pnl == null ? 'var(--text)' : pnl > 0 ? 'var(--up)' : pnl < 0 ? 'var(--down)' : 'var(--text)'
        return (
          <div key={code} style={{ padding: 8, borderRadius: 6, background: 'var(--bg-input)' }}>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Text strong>{code} {name}</Text>
              <Tag color={pnl != null && pnl >= 0 ? 'red' : 'green'}>{pnl != null ? `${pnl >= 0 ? '+' : ''}${(pnlPct ?? 0).toFixed(2)}%` : '—'}</Tag>
            </Space>
            <div style={{ fontSize: 12, marginTop: 4, color: 'var(--text-mute)' }}>
              持股 <Text strong style={{ color: 'var(--text)' }}>{shares.toLocaleString()}</Text> 股
              · 成本 <Text strong style={{ color: 'var(--text)' }}>{cost.toFixed(2)}</Text>
              · 现价 <Text strong style={{ color: 'var(--text)' }}>{price?.toFixed(2) ?? '—'}</Text>
              · 市值 <Text strong style={{ color: 'var(--text)' }}>{mv.toLocaleString()}</Text>
            </div>
            <div style={{ fontSize: 12, marginTop: 2, color: pnlColor }}>
              浮盈 {pnl != null ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)}` : '—'} 元
              · 止损 <Text type="danger">{String(sl)}</Text>
              · 止盈 <Text type="success">{String(tp)}</Text>
            </div>
          </div>
        )
      })}
    </div>
    <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
      行情最后更新：{quotes?.quote_time ?? '—'}（约 60s 缓存）
      · 监控定时 5 分钟轮询 / 手动「立即刷新监控」后自动更新
    </Text>
  </Card>
) : null}
```

**设计要点**：
- **卡片式网格布局**（auto-fill minmax 280px）——比 HoldingsPage 表格紧凑，每只持仓一卡，所有信息一眼可见
- **不引入新 LLM 分析**——所有字段都是 holdingQuotes 返回的原始数据，前端只做格式化
- **不引入新接口**——复用 HoldingsPage 已经在用的 holdingQuotes
- **标注数据来源时间**——`quote_time` 告诉用户这份数据的时效
- **标注刷新机制**——明确「监控定时 5 分钟轮询 / 手动触发后自动更新」，符合 sir 「不每次点击都分析更新」的需求

### 改动 3 — （可选）保留现有「移动止盈计划摘要」卡片

**不动现有卡片**（L138-150）。新卡和它互补：新卡展示「持仓静态 + 实时行情」概览，原卡展示「止盈计划档位建议」。两者信息来源不同（holdingQuotes vs takeProfitPlan 计算服务），sir 没有要求合并，**保持现状最小改动**。

## 红线（不可破）

- **不改动后端**：本工单不动 `backend/app/**` 任何文件、不新增接口、不修改 dashboard.py。
- **不改动 API 层**：本工单不动 `web/src/api/**` 任何文件（holdingQuotes 已存在）。
- **不改动类型定义**：本工单不动 `web/src/types/**` 任何文件，holding 字段用 `Record<string, unknown>` 索引签名访问。
- **不引入新依赖**：用现有 antd 的 `Card / Space / Tag / Typography`，不引入 dayjs/moment/echarts。
- **不触发 LLM 分析**：所有展示字段都从 holdingQuotes 直接读取，禁止任何 useTaskSubmit / mutate 调用。
- **不动「最新评分」卡片**（L160-168）：那是评分报告的概览，与本次需求无关。
- **不引入新缓存键**：复用 `['holding-quotes-overview']` 作为唯一 key；HoldingsPage 用的是 `['holding-quotes']`，key 不同不会冲突。
- **回滚**：若改动后页面出现异常（空白 / 报错 / 渲染抖动），执行 `git checkout -- web/src/pages/OverviewPage.tsx` 回滚本工单。

## 验收清单（必须全过）

1. `cd D:\self\web && npx tsc --noEmit` 通过，0 error。
2. `cd D:\self\web && npx oxlint src/pages/OverviewPage.tsx` 通过，0 error / 0 warn。
3. 浏览器进入 / 页面：
   - 「当前持仓概览」卡片出现在「移动止盈计划摘要」下方、「最新评分」上方
   - 每只持仓一卡，展示「代码+名称 / 涨幅 Tag / 持股 / 成本 / 现价 / 市值 / 浮盈 / 止损 / 止盈」共 9 项
   - 涨（pnl > 0）显示红色（`var(--up)` / Tag color=red），跌显示绿色（`var(--down)` / Tag color=green），符合中国 A 股惯例
   - 卡片底部显示「行情最后更新：YYYY-MM-DD HH:MM:SS（约 60s 缓存）」
   - 卡片底部显示「监控定时 5 分钟轮询 / 手动立即刷新监控后自动更新」
4. **不触发新 LLM 调用**：手动刷新页面时，右下角 TaskDrawer 不应出现新任务；浏览器 Network 面板 `holdingQuotes` 接口只调一次（queryFn 缓存命中）。
5. **手动触发「立即刷新监控（后台）」按钮**（OverviewPage 顶部）后，再次刷新页面 / 等 60s 自动 refetch，quote_time 应更新到当前时间。
6. **空状态**：当 holdings 为空（无持仓）时，卡片不渲染（`quotes?.rows?.length` 判定），不显示空白卡片。
7. **联动 HoldingsPage**：进入 /holdings 页面，操作 add/reduce/exit 后回到 /，OverviewPage 持仓列表应同步更新（同一 queryKey 缓存命中失效）。
8. 后端接口未新增 / 未修改：`/api/holdings/quotes`、`/api/dashboard` 调用参数不变。

## 交付要求

执行完成后回报：
- 修改的文件路径 + 改动行号区间
- tsc / oxlint 输出（截图或文本）
- 浏览器实测：进入首页截图（展示新持仓概览卡含具体信息）、空状态截图（如可构造空持仓场景）
- 验收清单 8 项逐条 ✅/❌ + 备注

未通过任意一项不算完成，继续修直到全过。