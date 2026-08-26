# CandidatesPage 优化（3 件事合并）

## 目标

`D:\self\web\src\pages\CandidatesPage.tsx` 单文件改：① 默认查当天；② 列表行加 AI 判定 Tag；③ Table 加「创建时间」列。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| L486 useState 之后 | 新增 `useEffect`：`if (!date && dates?.[0]) setDate(dates[0])` | dates 是异步数据，render 阶段不能 setState；与工单 10 同款写法 |
| L29 TIER_DOT 附近 | 新增 `LABEL_COLORS = { 可建仓:'green', 建议关注:'blue', 观察:'default' }` | 颜色按 React 现有 Tag 风格 |
| L611 「排名/股票」列 render | width 200→280，render 内读取 `tradeableMap[r.stock_code].label / block_reason`，加 Tag+Tooltip | Tooltip 内容：block_reason 存在则展示，否则"评级/现价/风险三条件均满足" |
| columns 数组「排名/股票」之后 | 插入 `{title:'创建时间', key:'trade_date', width:110, render: r => r.trade_date}` | trade_date = "创建时间"（候选池每日生成） |

## 红线

1. 不动后端 / API 层 / 类型定义
2. 不引入新依赖（不用 dayjs/moment）
3. tradeableMap 已在 L526-530 构建，render 内直接闭包引用，不再重查接口
4. 当 label 为空（tradeable 数据未落库）时 Tag 不渲染
5. 3 段筛选（全部 / 可建仓 / 观察）行为不变
6. 已有 LABEL_COLORS/TIER_MAP/QUICK_QUESTIONS 不重复定义

## 验收清单

- [ ] tsc --noEmit 0 error
- [ ] oxlint src/pages/CandidatesPage.tsx 0 error
- [ ] 首次进入 /candidates 自动展示当天候选（无空态）
- [ ] 列表行「排名/股票」右侧出现 AI 判定 Tag（绿/蓝/灰）
- [ ] 鼠标悬停 Tag 显示阻断原因或绿色文案
- [ ] Table 多「创建时间」列，值=r.trade_date
- [ ] 切 3 段筛选 Tag 颜色与文案同步刷新
