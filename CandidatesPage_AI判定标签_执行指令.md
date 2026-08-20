背景：sir 看 CandidatesPage 列表截图后反馈——AI 粗筛/细筛后的可建仓判定标签需要直接放到列表每只股票上，让用户不展开就能直观看到每只标的的"可建仓 / 建议关注 / 观察"三态判定。后端 candidateTradeable API 已返回 label + block_reason，React 现版顶部 stat card 用过这个数据但列表行未展示。

来源文件（已读）：
- D:\self\web\src\pages\CandidatesPage.tsx（L526-530 已构建 tradeableMap；L532-536 已用 is_tradeable === 1 筛选；L609-639 列表行未展示 AI 判定 Tag）
- D:\self\web\src\api\candidates.ts:13-14（candidateTradeable(date, limit=200) 返回 CandidateTradeable）
- D:\self\web\src\types\index.ts:112-120（CandidateTradeable.items 每项 Record<string, unknown>，含 is_tradeable / label / block_reason / cond_grade / cond_price / cond_risk / plan_exists / price_zone / current_price）
- D:\self\backend\app\services\candidate_tradeable.py:69-109（label 三态："可建仓"(is_tradeable=1) / "建议关注"(A/B 但买点未到) / "观察"(C 或无评分)；block_reason 是阻断原因拼接字符串）

改动 1 个文件：web\src\pages\CandidatesPage.tsx（648 行 → 约 670 行）。

整体策略：保持 React 现有 Tag + Tooltip 风格 + 交互范式，不引新依赖、不引 store、不改后端；不动 table 数据结构，只在「排名/股票」列（行号 + StockLabel 后）插入 AI 判定 Tag。

改动 ① 顶部常量表新增 LABEL_COLORS 映射（紧贴 L29-30 TIER_DOT 后追加）：

```tsx
const LABEL_COLORS: Record<string, string> = {
  '可建仓': 'green',
  '建议关注': 'blue',
  '观察': 'default',
}
```

改动 ② antd 顶部 import 追加 Tooltip（如未 import）。

改动 ③ L611-618 「排名/股票」列 render 替换为带 AI 判定 Tag 版本（width 280）：

当前代码 L611-618：
```tsx
{
  title: '排名/股票', key: 'stock', width: 200,
  render: (_: unknown, r: Candidate) => (
    <Space>
      <Text type="secondary">#{r.rank ?? '—'}</Text>
      <StockLabel code={r.stock_code} name={nameOf(r)} />
    </Space>
  ),
},
```

改为：

```tsx
{
  title: '排名/股票', key: 'stock', width: 280,
  render: (_: unknown, r: Candidate) => {
    const tv = (tradeableMap[r.stock_code] ?? {}) as Record<string, unknown>
    const label = String(tv.label ?? '')
    const block = String(tv.block_reason ?? '')
    return (
      <Space size={6} wrap>
        <Text type="secondary">#{r.rank ?? '—'}</Text>
        <StockLabel code={r.stock_code} name={nameOf(r)} />
        {label ? (
          <Tooltip
            title={block || '评级 / 现价 / 风险三条件均满足，建议进入建仓阶段'}
            placement="top"
          >
            <Tag color={LABEL_COLORS[label] ?? 'default'} style={{ marginInlineEnd: 0 }}>
              {label}
            </Tag>
          </Tooltip>
        ) : null}
      </Space>
    )
  },
},
```

tradeableMap 在外层 CandidatesPage 已构建（L526-530），本列 render 内可直接闭包引用。

改动 ④ 其他不动：评级列（L619-625）、3段筛选（L531-536）、BatchVerifyPanel、顶部 stat card、TraceModal 全部保持不变。

红线（全部硬约束）：
- 零改后端 routes.py / services / repo
- 零改 @/api/candidates.ts（接口已存在）
- 零改 types/index.ts（用 Record<string, unknown> 索引签名取 label / block_reason，无需新增字段）
- 零改 tasksStore / useTaskSubmit / 其他页面
- 零改 SideMenu / AppShell
- 零改 package.json
- 3段筛选（全部候选 / 可建仓 A+B / 观察 C）行为保持不变
- 不引入 zustand / 任何新状态库 / 任何新依赖
- 不搬 Streamlit 旧版的特殊行为（如 st.toast），统一沿用 React 现有 Tag + Tooltip 范式

回滚：

```bash
cd /d/self && git checkout HEAD -- web/src/pages/CandidatesPage.tsx
```

验收（全过才算完成）：
- [ ] cd D:\self\web && npx tsc --noEmit 0 error
- [ ] cd D:\self\web && npx oxlint src/pages/CandidatesPage.tsx 0 error 0 warning
- [ ] CandidatesPage 列表行每只股票「#N 股票名」右侧出现 AI 判定 Tag（颜色：可建仓=green / 建议关注=blue / 观察=default）
- [ ] 鼠标悬停 Tag 显示 tooltip：内容包含阻断原因（如"现价 X 偏离首仓区间..."）或"评级 / 现价 / 风险三条件均满足"绿色文案
- [ ] 切换筛选「全部候选 / 可建仓 A+B / 观察 C」时 Tag 颜色与文案随之变化（不报错、不消失）
- [ ] 当 tradeable 数据未落库（label 为空字符串）时，Tag 不渲染、不显示空白
- [ ] 顶部 stat card「今日可建仓标的」「可自动生成建仓计划」数值不变
