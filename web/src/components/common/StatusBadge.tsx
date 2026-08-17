interface StatusBadgeProps {
  text: string
  /** ok/active/green、info/processing/blue、pending/warn/amber、err/rejected/red、mute/rolled_back/gray */
  tone?: string
}

/** 状态标签（对齐 Streamlit badge；pending 灰·processing 蓝·done 绿 等映射） */
export function StatusBadge({ text, tone = 'mute' }: StatusBadgeProps) {
  const cls = tone || 'mute'
  return <span className={`st-badge ${cls}`}>{text}</span>
}

/** 状态 → 中文标签 + tone 映射（对齐 Streamlit _STATUS_LABEL/_STATUS_DOT） */
export const STATUS_MAP: Record<string, { label: string; tone: string }> = {
  pending: { label: '待识别', tone: 'pending' },
  processing: { label: '识别中', tone: 'processing' },
  done: { label: '已完成', tone: 'ok' },
  pending_review: { label: '待审核', tone: 'pending' },
  active: { label: '已生效', tone: 'active' },
  rejected: { label: '已驳回', tone: 'rejected' },
  rolled_back: { label: '已回滚', tone: 'rolled_back' },
}

/** 快捷：按状态 key 渲染徽章 */
export function StatusBadgeByKey(status?: string) {
  const m = STATUS_MAP[status ?? ''] ?? { label: status ?? '—', tone: 'mute' }
  return <StatusBadge text={m.label} tone={m.tone} />
}
