interface ConfidenceBarProps {
  confidence: number
  caption?: string
}

/**
 * 置信度进度条（对齐 Streamlit _conf_bar）：
 * ≥0.85 绿 / 0.5-0.85 琥珀 / <0.5 灰
 */
export function ConfidenceBar({ confidence, caption }: ConfidenceBarProps) {
  const conf = Math.max(0, Math.min(1, Number(confidence) || 0))
  const cls = conf >= 0.85 ? 'high' : conf >= 0.5 ? 'mid' : 'low'
  const pct = Math.round(conf * 100)
  return (
    <div>
      <div className="conf-bar">
        <div className={`conf-bar-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="conf-caption">{caption ?? `置信度 ${conf.toFixed(2)}`}</div>
    </div>
  )
}
