import { Typography, Tag } from 'antd'

interface PagePlaceholderProps {
  name: string
  phase?: string
  desc?: string
}

/** 占位页面（Phase 1 外壳验证用；Phase 2+ 逐个替换为真实页面） */
export function PagePlaceholder({ name, phase = 'Phase 2/3/4', desc }: PagePlaceholderProps) {
  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        {name}
        <Tag color="blue" style={{ marginLeft: 12, fontSize: 12 }}>{phase} 实装</Tag>
      </Typography.Title>
      <div className="st-empty">
        <span className="empty-icon">🚧</span>
        <div>{desc ?? `${name} 页面将在后续阶段实装，当前为工程外壳占位。`}</div>
      </div>
    </div>
  )
}
