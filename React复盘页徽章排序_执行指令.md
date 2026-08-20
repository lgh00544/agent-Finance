# React 复盘页「选股准确率验证」加徽章 + 排序 · Claude Code 执行指令

> **作者**：Lark
> **日期**：2026-08-20
> **改动范围**：仅 1 个 React 前端文件 + 1 个组件引用
> **依据**：Streamlit 旧前端已有 `D:\self\选股效果验证_排序加徽章_执行指令.md`（未执行）；React 新前端当前 Table 列只有 `股票/选中日/T+3/T+5/T+10/最大回撤`，无徽章无排序

---

## 1. 背景

sir 在 React 新前端「交易复盘 → 选股准确率验证」Tab 的 Table 上发现两个缺口：

| 缺口 | 现状 | 对照项 |
|---|---|---|
| ① 缺「可建仓/建议关注/观察」徽章 | Table 列只有股票 + T+N 涨跌幅 + 回撤，**无建仓级别** | `CandidatesPage.tsx:526-530` 已有 `tradeableMap` 按 `stock_code` 索引徽章；Streamlit `1_每日候选池.py:215-217` `_badge_html` |
| ② 缺排序控件 | Table 用 `pagination.pageSize=10` + 固定列序，**完全无排序** | Streamlit 指令 §3.3 提供了 4 档排序（评级/选中日/涨跌幅/回撤）；React 当前仅有日期选择下拉 |

**核心事实**：track_verify 行没有内嵌 `label`，需要按 `(select_date, stock_code)` 跨查 `candidate_tradeable` 表的历史判定。Streamlit 那边用 `api.candidate_tradeable(date=select_date)` 批量跨查；React 已有 `candidateTradeable(date, limit)` API，直接复用。

---

## 2. 红线（强制遵守）

| 红线 | 验证 |
|---|---|
| **只改 2 个文件**：`web/src/pages/ReviewsPage.tsx` + 必要时 `web/src/components/common/StatusBadge.tsx`（**不修改** `CandidatesPage.tsx`、不动后端、不动 Streamlit） | `git diff --name-only HEAD~1` 应只列这两文件 |
| **只读 candidate_tradeable**——不调判定、不补算、不传 tradeable_view() | 禁用 `apiClient` 任何写路径；只读 query |
| **不修改 trading 规则、研判标准、track_verify 算法** | 后端 `track_verify.py` 零改动 |
| **不动 Streamlit 任何文件** | 旧前端 streamlit/pages/* 零改动 |
| **改动可回滚** | 改动前 `cp ReviewsPage.tsx ReviewsPage.tsx.bak.tv_badge_sort` |
| **不破坏既有行为** | 日期选择 / 手动验证 / 生成建议 / StatCardGrid（胜率、平均涨幅、盈亏比、样本量）行为零回归 |

---

## 3. 详细规格

### 3.1 引入 import

在 `web/src/pages/ReviewsPage.tsx` 顶部（已有 `import { trackVerifyDates, trackVerifyList, trackVerifyStats, runTrackVerify, runTrackSuggest } from '@/api/track'` 那一行附近）追加：

```ts
import { candidateTradeable } from '@/api/candidates'
import type { CandidateTradeableItem } from '@/types'
```

如有同名 import 已存在则合并；不要重复。

### 3.2 类型补充（`web/src/types/index.ts`，仅注释，不改结构）

打开 `CandidateTradeableItem` 类型定义，**只加注释**，不增字段：

```ts
export interface CandidateTradeableItem {
  stock_code: string
  /** 判定标签（前端用），三态：'可建仓' | '建议关注' | '观察'。历史回填日期未落库时为空字符串。 */
  label?: string  // ← 若已有同名定义就保持，仅加 JSDoc
  is_tradeable?: number
  tier?: string
  price_zone?: string
  block_reason?: string
  [k: string]: unknown
}
```

**前提**：`web/src/types/index.ts` 当前已有 `CandidateTradeableItem` 定义（之前 `CandidatesPage.tsx` 已用）。若已存在同名，仅在 JSDoc 加注释；不要新增重复类型。

### 3.3 重写 `TrackVerify` 组件

完整替换 `ReviewsPage.tsx:106-151` 的 `TrackVerify` 函数。**核心改动**：

1. **批量跨查徽章**：`useQuery` 一次性取所有 distinct `select_date` 的 `candidateTradeable(date)`，按 `select_date_stock_code` 建索引
2. **Table 新增「建仓级别」列**：用 `StatusBadge`（或 inline `<span className={cls}>`）渲染 `可建仓/建议关注/观察` 彩色徽章
3. **Table 新增「排序」控件**：4 档，**默认「评级 + 选中日」**
4. **保留**既有 StatCardGrid、日期下拉、手动验证/生成建议按钮

**完整替换代码**（替换原 `TrackVerify` 函数体）：

```tsx
/** 选股准确率验证（track verify，直调） */
function TrackVerify() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [date, setDate] = useState<string>()
  const [sortKey, setSortKey] = useState<string>('rating-date')

  const { data: dates } = useQuery({ queryKey: ['tv-dates'], queryFn: () => trackVerifyDates() })
  const { data: rows } = useQuery({
    queryKey: ['tv-list', date],
    queryFn: () => trackVerifyList(date ?? ''),
    enabled: !!date || !!dates?.length,
  })
  const { data: stats } = useQuery({ queryKey: ['tv-stats'], queryFn: () => trackVerifyStats('t5') })

  // —— 新增：按 select_date 批量跨查 candidate_tradeable，构建徽章索引 —— 只读
  const distinctDates = useMemo(() => {
    const s = new Set<string>()
    for (const r of rows ?? []) {
      const sd = String((r as Record<string, unknown>).select_date ?? '')
      if (sd) s.add(sd)
    }
    return Array.from(s)
  }, [rows])

  const tradeableQueries = useQueries({
    queries: distinctDates.map((d) => ({
      queryKey: ['candidate-tradeable', d],
      queryFn: () => candidateTradeable(d, 200),
      enabled: distinctDates.length > 0,
      staleTime: 60_000,
      retry: 1,
    })),
  })

  const tradeableMap = useMemo(() => {
    const m = new Map<string, CandidateTradeableItem>()
    for (const q of tradeableQueries) {
      const items = (q.data?.items ?? []) as CandidateTradeableItem[]
      for (const it of items) {
        const code = String(it.stock_code ?? '')
        const d = String(q.data?.date ?? '')
        if (code && d) m.set(`${d}_${code}`, it)
      }
    }
    return m
  }, [tradeableQueries])

  // —— 新增：排序（前端 stable sort，不动后端默认顺序）
  const sortedRows = useMemo(() => {
    const list = (rows ?? []) as Record<string, unknown>[]
    const arr = [...list]
    const ratingWeight = (v: unknown): number => {
      const r = String(v ?? '').trim()
      if (r === 'A') return 0
      if (r === 'B') return 1
      if (r === 'C') return 2
      return 3
    }
    const getPct = (r: Record<string, unknown>, k: string): number | null => {
      const v = r[k]
      if (v == null) return null
      const n = typeof v === 'number' ? v : Number(v)
      return Number.isFinite(n) ? n : null
    }
    if (sortKey === 'rating-date') {
      arr.sort((a, b) => {
        const ra = ratingWeight(a.select_rating)
        const rb = ratingWeight(b.select_rating)
        if (ra !== rb) return ra - rb
        return String(a.select_date ?? '').localeCompare(String(b.select_date ?? ''))
      })
    } else if (sortKey === 'date-rating') {
      arr.sort((a, b) => {
        const da = String(a.select_date ?? '')
        const db = String(b.select_date ?? '')
        if (da !== db) return db.localeCompare(da)  // 选中日降序
        return ratingWeight(a.select_rating) - ratingWeight(b.select_rating)
      })
    } else if (sortKey === 't5-desc') {
      arr.sort((a, b) => (getPct(b, 't5_pct') ?? -999) - (getPct(a, 't5_pct') ?? -999))
    } else if (sortKey === 'dd-desc') {
      arr.sort((a, b) => (Number(b.max_drawdown ?? -999)) - (Number(a.max_drawdown ?? -999)))
    }
    return arr
  }, [rows, sortKey])

  const wr = stats?.win_rate
  const avg = stats?.avg_pct
  const runVerify = async () => { try { await runTrackVerify(false); message.success('T+N 验证已提交后台'); qc.invalidateQueries({ queryKey: ['tv-list'] }) } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }
  const runSuggest = async () => { try { await runTrackSuggest(); message.success('建议生成已提交后台') } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }

  // 徽章样式：与 CandidatesPage 的 st-badge 系列同源
  const badgeCls = (label?: string): string => {
    if (label === '可建仓') return 'ok'
    if (label === '建议关注') return 'info'
    if (label === '观察') return 'mute'
    return 'mute'
  }
  const renderBadge = (sd: string, code: string) => {
    const it = tradeableMap.get(`${sd}_${code}`)
    const label = it?.label
    if (!label) return <span style={{ color: '#bbb' }}>—</span>
    return <span className={`st-badge ${badgeCls(label)}`}>{label}</span>
  }

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select placeholder="选择日期" style={{ width: 140 }} value={date ?? dates?.[0]} onChange={setDate}
          options={(dates ?? []).map((d) => ({ label: d, value: d }))} />
        <Select
          placeholder="排序"
          style={{ width: 200 }}
          value={sortKey}
          onChange={setSortKey}
          options={[
            { label: '评级 A→C + 选中日', value: 'rating-date' },
            { label: '选中日降序 + 评级', value: 'date-rating' },
            { label: 'T+5 涨跌幅 高→低', value: 't5-desc' },
            { label: '最大回撤 高→低', value: 'dd-desc' },
          ]}
        />
        <Button onClick={runVerify}>手动验证（T+N）</Button>
        <Button onClick={runSuggest}>生成建议</Button>
      </Space>
      <StatCardGrid>
        <StatCard label="胜率" value={wr != null ? `${wr.toFixed(1)}%` : '无数据'}
          tone={wr != null ? (wr >= 50 ? 'ok' : wr < 40 ? 'err' : 'warn') : 'mute'}
          sub={`盈利 ${stats?.wins ?? 0} 笔 / 共 ${stats?.n ?? 0} 笔`} />
        <StatCard label="平均涨幅" value={avg != null ? `${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%` : '无数据'}
          tone={avg != null ? (avg > 0 ? 'up' : avg < 0 ? 'down' : 'mute') : 'mute'} />
        <StatCard label="盈亏比" value={stats?.pl_ratio != null ? stats.pl_ratio.toFixed(2) : '—'} tone="mute" />
        <StatCard label="样本量" value={stats?.n ?? 0} tone="mute" sub="T+5 已到期" />
      </StatCardGrid>
      <Table size="small" rowKey="id" dataSource={sortedRows} pagination={{ pageSize: 10 }}
        columns={[
          { title: '股票', key: 'stock', render: (_: unknown, r: Record<string, unknown>) => <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} /> },
          { title: '评级', dataIndex: 'select_rating', width: 70 },
          {
            title: '建仓级别',
            key: 'tradeable_label',
            width: 110,
            render: (_: unknown, r: Record<string, unknown>) =>
              renderBadge(String(r.select_date ?? ''), String(r.stock_code ?? '')),
          },
          { title: '选中日', dataIndex: 'select_date', width: 100 },
          { title: 'T+3', dataIndex: 't3_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: 'T+5', dataIndex: 't5_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: 'T+10', dataIndex: 't10_pct', width: 80, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: '最大回撤%', dataIndex: 'max_drawdown', width: 90, render: (v: unknown) => v ?? '—' },
        ]} />
    </div>
  )
}
```

### 3.4 import 追加校验

确保 `ReviewsPage.tsx` 顶部已引入：
- `useQueries` — `import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'`
- `useMemo` — 若未从 `react` 引入，则加 `useMemo` 到现有 `import { useState } from 'react'`

**禁止**额外引入第三方 UI 库（如 antd `Segmented`）；4 档排序用 antd `Select`（页面已用）。

---

## 4. 验收清单

### 4.1 功能验收（手动）

- [ ] npm run build 0 error
- [ ] tsc --noEmit 0 error
- [ ] 浏览器打开 React 复盘页 → 选股准确率验证 Tab
- [ ] Table 多出「评级」「建仓级别」两列
- [ ] 每行的「建仓级别」显示可建仓/建议关注/观察 彩色徽章（绿/蓝/灰）；**历史回填日期无 label 时显示 — 不刷灰色徽章**
- [ ] 排序下拉默认「评级 A→C + 选中日」，Table 行顺序：A 级在最前，组内按选中日升序
- [ ] 切「选中日降序 + 评级」→ 选中日 2026-08-19 排在 2026-08-12 之前
- [ ] 切「T+5 涨跌幅 高→低」→ T+5 涨幅大的在前；涨幅为 null 的行排到最后
- [ ] 切「最大回撤 高→低」→ 回撤大的在前
- [ ] 胜率 StatCard 仍显示 44.0%（不是 4400%——这是上条 React 前端胜率修复指令的活，本指令不动胜率）
- [ ] 既有「日期选择」「手动验证」「生成建议」按钮行为零回归
- [ ] Network 面板看 candidate-tradeable 的请求：distinctDates 多 → 多个并行 GET；同日期被 React Query 缓存 60s

### 4.2 静态验收

- [ ] `npx tsc --noEmit -p web/tsconfig.json` 0 error
- [ ] `grep -nE "tradeableMap|renderBadge|st-badge" web/src/pages/ReviewsPage.tsx | wc -l` ≥ 5
- [ ] `git diff --name-only HEAD` 仅出现 `web/src/pages/ReviewsPage.tsx`（和 `web/src/types/index.ts` 若改了注释）

---

## 5. 回滚

```bash
cp web/src/pages/ReviewsPage.tsx web/src/pages/ReviewsPage.tsx.bak.tv_badge_sort
# 若 types/index.ts 改过：
cp web/src/types/index.ts web/src/types/index.ts.bak.tv_badge_sort

# 回滚：
mv web/src/pages/ReviewsPage.tsx.bak.tv_badge_sort web/src/pages/ReviewsPage.tsx
mv web/src/types/index.ts.bak.tv_badge_sort web/src/types/index.ts   # 若有
```
