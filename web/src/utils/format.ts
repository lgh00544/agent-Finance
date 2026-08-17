/** 格式化工具（对齐 Streamlit render.py _bar_* 系列） */

/** 金额千分位（None/NaN → "—"） */
export function money(value: number | null | undefined): string {
  if (value == null || (typeof value === 'number' && Number.isNaN(value))) return '—'
  return value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** 带符号金额（+3,030.00 / -1,234.50） */
export function moneySigned(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value > 0 ? '+' : ''}${value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

/** 百分比（40.56 → "40.6%"；None → "—"） */
export function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(1)}%`
}

/** 百分比（数值百分数形式：40.56 → "40.6%"） */
export function pctOf(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(1)}%`
}

/** 涨跌符号（中国股市惯例：>0 红 up / <0 绿 down / 其余 flat） */
export function sign(value: number | null | undefined): 'up' | 'down' | 'flat' {
  if (value == null || Number.isNaN(value)) return 'flat'
  if (value > 0) return 'up'
  if (value < 0) return 'down'
  return 'flat'
}

/** 金额 → 万/亿（元，None/0 → "—"） */
export function moneyCn(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value) || value === 0) return '—'
  const f = Number(value)
  if (Math.abs(f) >= 1e8) return `${(f / 1e8).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}亿`
  return `${(f / 1e4).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}万`
}

/** 时间截断到分钟（YYYY-MM-DD HH:mm） */
export function shortTime(value?: string | null): string {
  return value ? String(value).slice(0, 16) : ''
}

/** 日期（YYYY-MM-DD） */
export function shortDate(value?: string | null): string {
  return value ? String(value).slice(0, 10) : ''
}
