# PaperTradingPanel·研究上下文展开内容布局修复（重发）_执行指令

> 说明：本指令 2026-09-10 首次发出，原 .md 已被清理，现按最新行号重发。

## 目标
`web/src/components/PaperTradingPanel.tsx`「研究上下文」Tab 展开行中：
- 工具表的「实时行情 / 日K线 / 新闻公告」等中文标签被强行竖排断字（`实/时/行/情`）
- 「已获取 30 条记录」挤在标签右侧看不全
- 嵌套表格列宽不足；"事实时点 / 记录时间"字号与其他字段不一致

根因：`ContextDetails` / `FactDetails` 内 `Descriptions column={1}` 嵌在父 Table `expandable` 中，label 列宽被压到极窄 + `overflowWrap: anywhere` → 强制逐字断行。

## 改动点

### 1. `ContextDetails`（line 169-186）
| 位置 | 改什么 |
|---|---|
| line 171 外层 div | 加 `background: 'var(--bg-input)'`，保留 padding 与 overflowWrap |
| line 172-175 Descriptions | `column={{ xs: 1, sm: 2 }}` → `column={{ xs: 1, sm: 2, md: 3 }}`，并加 `labelStyle={{ width: 120 }}` |
| line 176-185 子 Table | 各列加 width：`工具 110 / 结果 90 / 资料摘要 320`；`scroll={{ x: 500 }}` → `scroll={{ x: 760 }}` |
| line 183 摘要文案 | `${values.length} 条记录` → `${values.length} 条`（去掉"记录"减少挤压），并加 `Tooltip`（title 用 `fact?.note` 兜底"证据已记录"） |
| line 186 监控结论 | `<FactDetails value={{...}} />` 外包 `<Card size="small" title="监控结论 / 卖出研判">`，与上方工具表视觉分隔 |

### 2. `FactDetails`（line 151-167）
| 位置 | 改什么 |
|---|---|
| line 156 文本分支 | `<span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>` 改 `<Text style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>` |
| line 159 数组分支 | `size={8}` → `size={6}`；slice 上限保持 8 |
| line 163-166 Descriptions | `column={1}` → `column={{ xs: 1, sm: 2, md: 3 }}` + `labelStyle={{ width: 120 }}` |
| line 164 label 兜底 | `'补充资料'` → `'其他字段'` |

### 3. 主表补齐列宽（防止错位）
| 位置 | 改什么 |
|---|---|
| `executionColumns`（line 268-275） | 每列加 width：日期/事实时点 150、标的 110、方向 80、状态 110、数量/成交价 140、费用 100 |
| `contextColumns`（line 276-283） | 每列加 width：记录 80、交易日期 110、标的 100、研究模式 110、工具结果 140、联网来源 90、记录时间 150 |
| line 341 executions Table | `scroll={{ x: 880 }}` → `1000` |
| line 344 contexts Table | `scroll={{ x: 760 }}` → `880` |

## 红线
1. **不动后端/API/queryFn/数据结构**
2. **不动** `positions` Tab 的卡片网格（刚上线）、`evidence` / `alerts` 两个 Tab 的列
3. **不动** `FactDetails` / `ContextDetails` 的数据取值路径（`context.facts?.[row.tool]` 等）
4. 仅调整布局与文案，不加交互逻辑
5. 改动 ≤ 120 行，不新增文件

## 验收
1. 研究上下文 Tab 展开第 1 行：「实时行情 / 日K线」中文标签**水平完整显示**，不竖排断字
2. 工具表 3 列对齐：工具名完整 / 结果 Tag / 「30 条」+ Tooltip
3. 点展开箭头 → FactDetails 字段横排（label 在左、值在右，label 宽 120）
4. 「监控结论 / 卖出研判」包在独立 Card 内，与工具表有视觉分隔
5. 模拟流水 / 研究上下文两个 Tab 的表格不出现列错位
6. `tsc -b --force` EXIT=0；其他 4 个 Tab 功能不回归
