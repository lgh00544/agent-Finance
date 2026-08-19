import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { marketIndices } from '@/api/market'
import { health } from '@/api/system'
import { getExperienceList } from '@/api/experience'
import { holdingQuotes } from '@/api/holdings'
import { money, moneySigned, sign } from '@/utils/format'

/** 北京时间（每秒更新） */
function useBeijingTime() {
  const [now, setNow] = useState<string>(() => new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }))
  useEffect(() => {
    const t = setInterval(() => {
      setNow(new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }))
    }, 1000)
    return () => clearInterval(t)
  }, [])
  return now
}

/** 账户资产：从前端聚合 /api/holdings/quotes 的 rows。
 * 空持仓（rows 为空）→ 总资产=total_capital、其余 —；字段缺失/null → —，绝不报错。 */
function useHoldingAssets() {
  const { data } = useQuery({
    queryKey: ['holding-assets'],
    queryFn: holdingQuotes,
    refetchInterval: 30_000,
    staleTime: 25_000,
    retry: 0,
  })
  const rows = data?.rows ?? []
  let marketValue = 0
  let pnlAmount = 0
  let hasValue = false
  for (const r of rows) {
    const mv = r.market_value
    const pa = r.pnl_amount
    if (typeof mv === 'number' && Number.isFinite(mv)) {
      marketValue += mv
      hasValue = true
    }
    if (typeof pa === 'number' && Number.isFinite(pa)) pnlAmount += pa
  }
  const assets = {
    total: data && typeof data.total_capital === 'number' ? data.total_capital : null,
    marketValue: hasValue ? marketValue : null,
    pnlAmount: hasValue ? pnlAmount : null,
    available: hasValue ? (data?.total_capital != null ? data.total_capital - marketValue : null) : null,
  }
  return assets
}

/** 账户资产展示（指数区之后）：总资产/可用资金/持仓市值/持仓总盈亏/持仓盈亏比。 */
function AssetsBar() {
  const a = useHoldingAssets()
  const hasPositions = a.marketValue != null

  // 成本口径：盈亏比 = 总盈亏 / (持仓市值 − 总盈亏)；分母非正或数据缺失 → —
  let pnlPct: number | null = null
  if (hasPositions && a.pnlAmount != null && a.marketValue != null) {
    const cost = a.marketValue - a.pnlAmount
    if (cost > 0) pnlPct = (a.pnlAmount / cost) * 100
  }
  const pnlSign = sign(a.pnlAmount)
  const pnlCls = pnlSign === 'up' ? 'tsb-up' : pnlSign === 'down' ? 'tsb-down' : 'tsb-mute'

  return (
    <span className="tsb-assets">
      <span className="tsb-item">
        <span>总资产</span>
        <b>{a.total != null ? money(a.total) : '—'}</b>
      </span>
      <span className="tsb-item">
        <span>可用资金</span>
        <b>{a.available != null ? money(a.available) : '—'}</b>
      </span>
      <span className="tsb-item">
        <span>持仓市值</span>
        <b>{a.marketValue != null ? money(a.marketValue) : '—'}</b>
      </span>
      <span className="tsb-item">
        <span>持仓盈亏</span>
        <b className={pnlCls}>{a.pnlAmount != null ? moneySigned(a.pnlAmount) : '—'}</b>
      </span>
      <span className="tsb-item">
        <span>盈亏比</span>
        <b className={pnlCls}>{pnlPct != null ? `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%` : '—'}</b>
      </span>
    </span>
  )
}

/** 顶部状态栏：左=三大指数（涨红跌绿，30s 轮询）+ 账户资产；右=系统状态点 + 北京时间。
 * 接口失败优雅降级显示"—"，绝不白屏。 */
export function TopStatusBar() {
  const now = useBeijingTime()
  const { data: indices } = useQuery({
    queryKey: ['market-indices'],
    queryFn: marketIndices,
    refetchInterval: 30_000,
    staleTime: 25_000,
    retry: 0,
  })
  const { data: sysHealth } = useQuery({
    queryKey: ['health'],
    queryFn: health,
    refetchInterval: 30_000,
    staleTime: 25_000,
    retry: 0,
  })
  // 经验待审核徽章：60s 节流（staleTime 60s + refetchInterval 60s），list 长度近似；
  // 接口失败 select 抛错 → data 为 undefined → 徽章隐藏（静默降级不显示不报错）
  const { data: expPending = undefined } = useQuery({
    queryKey: ['exp-pending-review-count'],
    queryFn: () => getExperienceList('pending_review', undefined, undefined, 1000),
    refetchInterval: 60_000,
    staleTime: 60_000,
    retry: 0,
    select: (rows) => (rows ?? []).length,
  })

  const list = indices?.indices ?? []
  const ok = !!sysHealth && sysHealth.status === 'ok'

  return (
    <div className="top-status-bar">
      {list.length === 0 ? (
        <span className="tsb-item">
          指数 <b className="tsb-mute">—</b>
        </span>
      ) : (
        list.slice(0, 3).map((it) => {
          const s = sign(it.change_pct)
          const cls = s === 'up' ? 'tsb-up' : s === 'down' ? 'tsb-down' : 'tsb-mute'
          return (
            <span className="tsb-item" key={it.code ?? it.name}>
              <span>{it.name}</span>
              <b className={cls}>
                {it.price != null ? money(it.price) : '—'}
                {it.change_pct != null ? ` ${it.change_pct >= 0 ? '+' : ''}${it.change_pct.toFixed(2)}%` : ''}
              </b>
            </span>
          )
        })
      )}
      <AssetsBar />
      <span style={{ flex: 1 }} />
      <span className="tsb-item">
        <span className={ok ? 'tsb-ok-dot' : 'tsb-err-dot'} />
        系统{ok ? '正常' : '异常'}
      </span>
      {expPending !== undefined ? (
        <span className="tsb-item">
          <span>经验待审核</span>
          <b className={expPending > 0 ? 'tsb-up' : 'tsb-mute'}>{expPending}</b>
        </span>
      ) : null}
      <span className="tsb-item">
        北京时间 <b>{now}</b>
      </span>
    </div>
  )
}
