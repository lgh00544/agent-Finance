import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, Spin, Typography } from 'antd'
import { authStatus, login, type AuthStatus } from '@/api/auth'
import { setAuthToken } from '@/api/client'

const { Title, Text } = Typography

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      setStatus(await authStatus())
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void refresh() }, [])

  if (loading) return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}><Spin /></div>
  if (!status?.multi_user_enabled || status.user_id != null) return <>{children}</>

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <Card style={{ width: 360, maxWidth: '100%' }}>
        <Title level={3} style={{ marginTop: 0 }}>A股决策 Agent</Title>
        <Text type="secondary">请输入账户凭据登录多人工作区</Text>
        {error ? <Alert type="error" showIcon message={error} style={{ marginTop: 16 }} /> : null}
        <Form layout="vertical" style={{ marginTop: 16 }} onFinish={async (values) => {
          setSubmitting(true)
          try {
            const result = await login(values.username, values.password)
            setAuthToken(result.access_token)
            await refresh()
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err))
          } finally {
            setSubmitting(false)
          }
        }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting} block>登录</Button>
        </Form>
      </Card>
    </div>
  )
}
