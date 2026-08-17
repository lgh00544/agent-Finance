import { Button } from 'antd'

interface EmptyStateProps {
  text: string
  icon?: string
  actionLabel?: string
  onAction?: () => void
}

/** 空态（图标+说明+可选操作按钮，虚线框居中） */
export function EmptyState({ text, icon = '📭', actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="st-empty">
      <span className="empty-icon">{icon}</span>
      <div>{text}</div>
      {actionLabel ? (
        <Button size="small" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  )
}

/** 错误卡（标题+详情+重试按钮；接收 React Query 的 error 或 message） */
export function ErrorCard({
  title,
  message,
  detail,
  onRetry,
}: {
  title: string
  message?: string
  detail?: string
  onRetry?: () => void
}) {
  return (
    <div className="st-error-card">
      <div>
        <div className="err-title">⛔ {title}</div>
        {message ? <div className="err-body">{message}</div> : null}
        {detail ? <div className="err-body">{detail}</div> : null}
        {onRetry ? (
          <Button size="small" style={{ marginTop: 8 }} onClick={onRetry}>
            重试
          </Button>
        ) : null}
      </div>
    </div>
  )
}

/** 从 React Query error 提取消息（含 ConflictError） */
export function errorMsg(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}
