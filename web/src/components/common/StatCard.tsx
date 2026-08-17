import type { ReactNode } from 'react'
import './common.css'

interface StatCardProps {
  label: string
  value: ReactNode
  sub?: string
  /** up=红(涨/盈) down=绿(跌/亏) ok/warn/err/mute */
  tone?: 'up' | 'down' | 'ok' | 'warn' | 'err' | 'mute'
}

/** 指标卡（标题+数值+副文，支持涨跌色；对齐 Streamlit stat_cards） */
export function StatCard({ label, value, sub, tone = 'mute' }: StatCardProps) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone}`}>{value}</div>
      {sub ? <div className="stat-sub">{sub}</div> : null}
    </div>
  )
}

/** 指标卡网格容器 */
export function StatCardGrid({ children }: { children: ReactNode }) {
  return <div className="stat-grid">{children}</div>
}
