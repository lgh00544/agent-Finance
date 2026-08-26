# 工单12 HoldingsPage 补全

## 目标
补齐 HoldingsPage「告警记录」tab 里的**组合哨兵告警独立区块**（当前全量告警混排，缺组合级风控分组展示）。**仅改 web/src/pages/HoldingsPage.tsx 单文件**，后端/API/类型零改动（接口实存：alerts(limit) 返回含 source 字段的 AlertInfo[]）。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| AlertsTab 组件（当前 L668 全量表格） | 顶部加「组合哨兵告警」区块：从 data 过滤 `source==='portfolio_sentinel'`，卡片化展示（板块退潮/时间止损/组合回撤/集中度 信号 + 红色 Tag「组合级风控」），空则显示「暂无组合哨兵告警」 | 对齐旧版 L736-771 语义 |
| AlertsTab 表格 | 表格保留（下方全量告警），但仅展示非哨兵告警 OR 标注；顶部加过滤 Toggle（全部/组合哨兵/持仓监控） | 红涨绿跌 |

## 红线

1. 只改 `web/src/pages/HoldingsPage.tsx`；禁止动 backend / api/alerts.ts / types
2. 不新增依赖（仅 antd 已有：Card/Tag/Alert/EmptyState/Tooltip）
3. 复用现有 AlertsTab 的 useQuery(alerts) 数据；不额外请求
4. 空数据不渲染或「暂无」；不编造 source 值（严格 === 匹配）
5. 已存在的操作编辑/OCR/建仓/红线/离场组件一律不动

## 验收清单

- [ ] 告警 tab 顶部出现「组合哨兵告警」独立区块（source=portfolio_sentinel 过滤）
- [ ] 哨兵告警卡片展示板块/类型/时间，标记「组合级风控」
- [ ] 无哨兵告警时显示空态文案
- [ ] 下方全量告警表格保留；过滤切换可用
- [ ] tsc -b + npm build 0 error；oxlint 0 error
- [ ] 提交为 `feat(holdings): 告警页补组合哨兵分组`，单文件

## 参考
- 旧版：D:\self\streamlit\pages\4_持仓监控.py L736-771（sentinel_rows 过滤 + alert_list）
- 类型：web/src/types/index.ts AlertInfo（含 source / alert_type / message）
- API：web/src/api/alerts.ts:5 `alerts(limit)` 返回 AlertInfo[]