# 经验沉淀 M4 经验库浏览器

## 目标
`web/src/pages/ExperiencePage.tsx` 现有 M1 沉淀队列 / M2 Digest / M3 高影响审核 / M5 设置 四个 tab，**缺 M4 经验库浏览器**。补一个「经验库」tab，可检索、筛选、查看已沉淀经验（含回滚入口）。纯前端单文件，后端/API/类型零改动。

## 现状（已核实）

- tab 数组在 L475-480：M1/M2/M3/M5 已齐，`{ label: 'M4 经验库', value: 'M4' }` 未加
- API 全实存：`listExperience(stage?, status?, limit)`（`web/src/api/experience.ts` 有 `getExperienceList`）、`searchExperience(stage?, query?, k=50)`（FTS 检索）、`getExperienceDetail(eid)`、`rollbackExperience(eid)`、`reviewExperience(eid, action, note)`
- 类型 `Experience` 字段：id/title/body/stage/tags/impact('high'|'low')/confidence/auto_merged/status('pending_review'|'active'|'rejected'|'rolled_back')/created_at/last_reviewed_at/source_summary/source_task_id（`types/index.ts:460-476`）
- `searchExperience` 走 GET `/experience/search`，`getExperienceList` 走 `/experience/list`

## 改动点（仅 web/src/pages/ExperiencePage.tsx）

| 位置 | 改动 | 备注 |
|---|---|---|
| tab 数组 | 加 `{ label: 'M4 经验库', value: 'M4' }` | 插在 M3 与 M5 之间 |
| 新增 `ExpLibraryPanel` 组件 | 顶部：状态筛选（全部/生效/待审核/已驳回/已回滚）+ 阶段筛选 + 关键词搜索框（Enter 触发）；主体：经验卡片列表或 Table | 复用 `listExperience`/`searchExperience`；卡片复用现有 StatusBadge 逻辑（M3 已有） |
| 每条经验卡 | 标题 + 阶段 Tag + 影响高/低 + confidence + 状态 Tag + 创建时间 + 摘要（body 截断） | 高影响红色高亮 |
| 详情 | 点击卡片打开 Drawer/Modal 显示完整 body + source 信息 + 「回滚」（status=active 时，rollbackExperience）| 对齐 M3 详情交互 |
| 空态 | 无数据显示「暂无经验」EmptyState | 复用 |

## 红线
1. 只改 `web/src/pages/ExperiencePage.tsx`；禁动后端 / API / types / 其它 tab
2. 不新增依赖；复用已有组件（Card/Tag/Select/Input/Table/Drawer）+ 现有效果状态
3. 检索只调已有 `searchExperience`，不引新接口、不 bulk-load 全量入上下文

## 验收清单（≤6）
- [ ] `npx tsc --noEmit` 0 error + `npx oxlint` 0 error + `npm run build` EXIT=0
- [ ] 新增「M4 经验库」tab，渲染正常
- [ ] 状态/阶段筛选 + 关键词检索生效（复用已有 API）
- [ ] 经验卡显示阶段/影响/置信/状态/摘要；高影响高亮
- [ ] 点击展开详情（body/source/回滚入口，rolled_back 可回滚）
- [ ] 空态显示「暂无经验」；后端/API/类型零改动