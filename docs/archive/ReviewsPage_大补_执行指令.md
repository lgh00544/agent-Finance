# 工单 9：ReviewsPage 大补（对齐 Streamlit 旧版 1409 行功能密度）

## 目标

`D:\self\web\src\pages\ReviewsPage.tsx` 单文件从当前 496 行扩充到 1100+ 行，**按 React 现有交互模式**补齐 Streamlit 旧版（`streamlit/pages/2_交易复盘.py` 1409 行）的功能，不搬 streamlit-specific 行为。

## 改动点

| 区域 | 改动 | 备注 |
|---|---|---|
| 顶部 Tabs 第 4 个「策略闭环建议」 | 补全当前未实现的：① 选股效果验证 period/4 筛选（近 1/3/6/12 月 + 全部）；② 历史回填按钮（手动触发时显示） | 后端 `/api/reviews/track-verify?period=1m\|3m\|6m\|12m\|all` 已支持 |
| 中部组合归因 | 已实装，不动 | 批次 H 已提交 |
| 复盘详情 Drawer | 补全：① 完整推理留痕（trace_id 跳推理层）；② 多日盈亏曲线（按 exit_date - 30d 拉日 K） | 复用 trace API + ECharts |
| 底部 | 新增「每日组合总结」section（来自后端 `/api/portfolio/daily-summary`） | 现有 List 改为 Grid auto-fill |

## 红线

1. 不动后端 / API 层
2. 不引入新依赖（用现有 antd + ECharts）
3. 旧版的 streamlit-specific 行为（st.session_state、st.rerun、st.toast）**不搬**
4. 业务算法（统计阈值 / 胜率口径 / 归因公式）允许照搬
5. 已实装的 AI 自动决策 banner / Drawer / 驳回不动
6. 不删现有任何 React 组件
7. 体积上限 ≤ 1200 行（不能堆到 1500）

## 验收清单

- [ ] tsc --noEmit 0 error
- [ ] oxlint src/pages/ReviewsPage.tsx 0 error
- [ ] 「选股效果验证」Tab 出现 period 筛选（5 档）
- [ ] 复盘详情 Drawer 出现推理留痕 + 多日盈亏曲线
- [ ] 底部「每日组合总结」section 出现
- [ ] 文件总行数 1100-1200
- [ ] 已实装功能（AI banner / 驳回 / Drawer / ECharts 归因）零回归
