import { useEffect, useState } from 'react'
import { App, Button, Card, Col, Divider, Form, Input, InputNumber, Row, Space, Spin, Tag, Alert } from 'antd'
import { SaveOutlined, DownloadOutlined, UploadOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getProfile, putProfile, exportProfile, importProfile } from '@/api/profile'

type ExtraField = { key: string; value: string }

export default function ProfilePage() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const [form] = Form.useForm<Record<string, unknown>>()
  const [extras, setExtras] = useState<ExtraField[]>([])
  const [importText, setImportText] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => getProfile(),
  })

  useEffect(() => {
    if (!data) return
    form.setFieldsValue(data.content || {})
    const extraObj = (data.content?.extra as Record<string, unknown>) || {}
    setExtras(Object.entries(extraObj).map(([k, v]) => ({ key: k, value: String(v) })))
  }, [data, form])

  const handleSave = async () => {
    try {
      const v = await form.validateFields()
      const normalized: Record<string, unknown> = {
        max_position_pct: Number(v.max_position_pct ?? 0),
        stop_loss_pct: Number(v.stop_loss_pct ?? 0),
        take_profit_pct: v.take_profit_pct != null ? Number(v.take_profit_pct) : undefined,
        preferred_sectors: String(v.preferred_sectors ?? ''),
        watchlist: String(v.watchlist ?? ''),
      }
      const extraObj: Record<string, string> = {}
      extras.forEach(({ key, value }) => { if (key) extraObj[key] = value })
      if (Object.keys(extraObj).length) normalized.extra = extraObj
      await putProfile(normalized)
      message.success('已保存，版本号 +1')
      qc.invalidateQueries({ queryKey: ['profile'] })
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      message.error(`保存失败：${msg}`)
    }
  }

  const handleExport = async () => {
    try {
      const json = await exportProfile()
      const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `trade-profile-v${json.version ?? 0}-${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('已导出 JSON')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      message.error(`导出失败：${msg}`)
    }
  }

  const handleImport = async () => {
    if (!importText.trim()) { message.warning('请先粘贴 JSON'); return }
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(importText)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      message.error(`JSON 解析失败：${msg}`)
      return
    }
    const content = (parsed.content && typeof parsed.content === 'object')
      ? parsed.content as Record<string, unknown>
      : parsed
    const targetVersion = Number(parsed.version ?? 0) + 1
    modal.confirm({
      title: '确认导入',
      content: `将覆盖当前偏好（version → ${targetVersion}），继续？`,
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await importProfile(content)
          message.success('已导入，版本号 +1')
          setImportText('')
          qc.invalidateQueries({ queryKey: ['profile'] })
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : String(e)
          message.error(`导入失败：${msg}`)
        }
      },
    })
  }

  const addExtra = () => setExtras([...extras, { key: '', value: '' }])
  const removeExtra = (idx: number) => setExtras(extras.filter((_, i) => i !== idx))
  const updateExtra = (idx: number, patch: Partial<ExtraField>) =>
    setExtras(extras.map((f, i) => i === idx ? { ...f, ...patch } : f))

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '80px auto' }} />
  if (!data) return null

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card title="当前偏好" extra={<Tag color="blue">v{data.version ?? 0}</Tag>}>
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="max_position_pct" label="单股最大仓位(%)" rules={[{ required: true, type: 'number' }]}>
                <InputNumber min={0} max={100} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="stop_loss_pct" label="默认止损线(%)" rules={[{ required: true, type: 'number' }]}>
                <InputNumber min={0} max={50} step={0.5} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="take_profit_pct" label="默认止盈线(%)">
                <InputNumber min={0} max={200} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="preferred_sectors" label="偏好板块（逗号分隔，如 新能源,半导体,医药）">
            <Input placeholder="新能源,半导体,医药" />
          </Form.Item>
          <Form.Item name="watchlist" label="自选股代码（逗号分隔）">
            <Input placeholder="600519,000858,300750" />
          </Form.Item>
          <Divider>自定义偏好（key-value）</Divider>
          {extras.map((f, idx) => (
            <Row gutter={8} key={idx} style={{ marginBottom: 8 }}>
              <Col span={6}><Input placeholder="key" value={f.key} onChange={e => updateExtra(idx, { key: e.target.value })} /></Col>
              <Col span={16}><Input placeholder="value" value={f.value} onChange={e => updateExtra(idx, { value: e.target.value })} /></Col>
              <Col span={2}><Button danger icon={<DeleteOutlined />} onClick={() => removeExtra(idx)} /></Col>
            </Row>
          ))}
          <Button onClick={addExtra} icon={<PlusOutlined />}>添加字段</Button>
        </Form>
        <Divider />
        <Space>
          <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>保存（version +1）</Button>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出 JSON</Button>
        </Space>
      </Card>

      <Card title="导入偏好">
        <Alert type="info" message="粘贴之前导出的 JSON，确认后将覆盖当前偏好并把 version +1" style={{ marginBottom: 12 }} showIcon />
        <Input.TextArea rows={6} value={importText} onChange={e => setImportText(e.target.value)} placeholder='{"version": 3, "content": { ... }}' />
        <Button type="primary" danger icon={<UploadOutlined />} style={{ marginTop: 8 }} onClick={handleImport}>
          确认导入
        </Button>
      </Card>
    </Space>
  )
}
