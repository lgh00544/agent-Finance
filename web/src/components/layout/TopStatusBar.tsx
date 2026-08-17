import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { marketIndices } from '@/api/market'
import { health } from '@/api/system'
import { money, sign } from '@/utils/format'

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

/** 顶部状态栏：左=三大指数（涨红跌绿，30s 轮询）；右=系统状态点 + 北京时间。
 * 接口失败优雅降级显示"—"，绝不白屏。 */
export function TopStatusBar() {
  const now = useBeijingTime()
  const { data: indices } = useQuery({
    queryKey: ['market-indices'],
    queryFn: marketIndices,
    refetchInterval: 30_000,
    staleTime: 25_000,
    retry: 1,
  })
  const { data: sysHealth } = useQuery({
    queryKey: ['health'],
    queryFn: health,
    refetchInterval: 30_000,
    staleTime: 25_000,
    retry: 1,
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
      <span style={{ flex: 1 }} />
      <span className="tsb-item">
        <span className={ok ? 'tsb-ok-dot' : 'tsb-err-dot'} />
        系统{ok ? '正常' : '异常'}
      </span>
      <span className="tsb-item">
        北京时间 <b>{now}</b>
      </span>
    </div>
  )
}
