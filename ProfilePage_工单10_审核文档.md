# 工单 10：新建 ProfilePage（个人交易偏好）· 工程师审核

> **作者**：Lark
> **日期**：2026-08-20
> **审核范围**：仅 3 个前端文件（1 新建 + 2 接入），零后端改动

---

## 1. 背景

v2 全面盘点发现 `streamlit/pages/7_个人交易偏好.py`（104 行）在 React 端**整页漏迁**——`@/api/profile.ts` 4 个函数（getProfile/putProfile/exportProfile/importProfile）都写好了、后端 routes.py:785-813 4 个端点也都实现了，但**没有 React 页面**也没有**导航入口**。这是 v2 优先级 P0 的工单——必须最先做，因为用户在 TopStatusBar 设置区也找不到个人偏好的入口。

## 2. 改动清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `D:\self\web\src\pages\ProfilePage.tsx` | **新建**，编辑表单 + 导出/导入 |
| 2 | `D:\self\web\src\App.tsx` | 加 `ProfilePage` lazy + 路由 `<Route path="profile">` |
| 3 | `D:\self\web\src\components\layout\SideMenu.tsx` | 第 4 组「策略沉淀」加一项 |

**严格红线**：
- 零后端改动（Python / SQL / 配置零改）
- 零 store 新增（zustand 不需要，仅靠 react-query）
- 零新依赖（Form/Input/Button/Upload 等 antd 6.6.1 自带）
- 零新组件库（仍走 antd + react-query 现有栈）

## 3. 详细规格

### 3.1 `pages/ProfilePage.tsx`（新建，预计 130-160 行）

**组件结构**：
- `EditPanel`（主）：表单动态渲染所有字段 + 新增字段 + 保存
- `ImportExportPanel`（次）：导出 JSON / 导入 JSON（双列布局）

**EditPanel 关键逻辑**：
- `useQuery(['profile'], getProfile)` 拉 `{version, content}` → `version` 显示顶部 `当前版本：vN`
- 遍历 `content` 字段，按类型渲染控件：
  - `number` → `<InputNumber>`
  - `object`/`array` → `<Input.TextArea>`（预填 `JSON.stringify(v, null, 2)`）
  - `string` → `<Input>`（含字符串型 boolean 显示"true"/"false"）
- 保存按钮：组装 `edited` 对象 → `putProfile(content)` → 成功后 `message.success` + `qc.invalidateQueries(['profile'])`
- 新增字段：2 个 `<Input>`（key + value），value 用 `JSON.parse` 试解析（不合法就当字符串存）
- **不重置 `form` 实例**——保留用户编辑，保存成功后才 `qc.invalidateQueries` 拉最新

**ImportExportPanel 关键逻辑**：
- 左列：`<Button onClick={handleExport}>` → 调 `exportProfile()` → 调 `api/client.ts` 的 `download` 工具或 `URL.createObjectURL(blob)` 触发下载（参考 ExperiencePage.tsx 导出模式）
- 右列：`<Upload accept=".json" beforeUpload={handleImport}>` → FileReader 读文本 → `JSON.parse` → 校验 `content` 字段 → 调 `importProfile(content)` → toast + invalidate

**错误处理**：
- API 失败（5xx/4xx）→ `message.error(e.message)`
- 解析失败 → `message.warning('字段值不是合法 JSON，已按字符串保存')`

**文件位置**：`D:\self\web\src\pages\ProfilePage.tsx`

### 3.2 `App.tsx` 接入

**改动 ①**（L1-19 的 lazy 块）：在 `ExperiencePage` 之后追加：
```tsx
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))
```

**改动 ②**（L48 之后、`/*` 之前）：加路由：
```tsx
<Route path="profile" element={<ProfilePage />} />
```

**文件位置**：`D:\self\web\src\App.tsx` L19 之后 / L48 之后

### 3.3 `SideMenu.tsx` 加导航

**改动 ①**（L2-15 import）：加 `UserOutlined`：
```tsx
import {
  ...
  UserOutlined,  // 新增
} from '@ant-design/icons'
```

**改动 ②**（L60-65 第 4 组「策略沉淀」）：在 `experience` 之前追加：
```tsx
{ path: '/profile', label: '个人交易偏好', icon: <UserOutlined /> },
```

**文件位置**：`D:\self\web\src\components\layout\SideMenu.tsx`

---

## 4. 验收清单

### 4.1 功能验收（手动跑）

- [ ] `App.tsx` 编译通过，路由 `profile` 出现在 L48 之后
- [ ] `SideMenu.tsx` 第 4 组「策略沉淀」下出现「个人交易偏好」菜单项
- [ ] 浏览器访问 `/profile` 页面正常加载（不报 chunk 错误）
- [ ] 顶部显示「当前版本：vN」（N 是后端当前 version）
- [ ] 表单渲染所有后端返回的 content 字段，按类型正确选择控件
- [ ] 修改某字段值 → 点「保存」→ 顶部 version+1 → toast「已保存，版本 vN+1」
- [ ] 「新增字段」输入 key+value → 保存 → 新字段出现在表单
- [ ] 「导出 JSON」按钮触发浏览器下载，文件名为 `trade_profile.json` 或 `profile_vN.json`
- [ ] 「导入 JSON」上传之前导出的文件 → 顶部 version+1 + toast「导入成功，版本 vN+1」
- [ ] 导入非法 JSON（无 content 字段）→ toast「导入文件格式不符」不崩溃
- [ ] 后端失败（PUT 400）→ 红色 toast 显示后端 detail，表单内容保留不重置

### 4.2 类型/编译验收

- [ ] `tsc --noEmit` 0 error
- [ ] `npx oxlint src/pages/ProfilePage.tsx src/App.tsx src/components/layout/SideMenu.tsx` 0 error
- [ ] antd 组件（Form/Input/InputNumber/Button/Upload/Alert）全部命中现有 6.6.1 版本
- [ ] `TradeProfile` / `getProfile` / `putProfile` / `exportProfile` / `importProfile` 全部从 `@/api/profile` import，不重新定义类型

### 4.3 回归验收

- [ ] 既有的 13 路由不破坏（lazy 加载顺序不影响）
- [ ] SideMenu 4 组 13 项菜单顺序不乱
- [ ] 字段值类型自动识别（number/object/array/string）逻辑覆盖 4 种类型

---

## 5. 红线（必须遵守）

| 红线 | 验证方式 |
|---|---|
| **不动后端** | `backend/` 路径下零文件改动 |
| **不新增 store** | `web/src/store/` 路径下零文件改动 |
| **不修改 AppShell 布局** | `AppShell.tsx` 零改动（仅 TopStatusBar/SideMenu/TaskDrawer） |
| **不引入新依赖** | `package.json` 零改动 |
| **不替换 UI 库** | 仍走 antd + react-query |
| **不破坏既有 13 路由** | 仅追加 `profile` 路由，零删除零修改 |
| **导入失败不崩** | 错误 toast 即可，表单内容保留 |

---

## 6. 回滚方案

| 失败点 | 回滚 |
|---|---|
| 字段类型识别错（object 字段被当 string） | 调整 `typeof v === 'object' && v !== null` 判定 |
| 导入文件解析失败 | 加重 `try/catch` 包裹整个 handleImport |
| SideMenu 顺序难看 | 调换 items 顺序（在 experience 前/后） |
| 整体执行失败 | 删 ProfilePage.tsx + App.tsx 移除 2 行 + SideMenu 移除 1 项 |

---

## 7. 实施顺序（建议 4 步）

1. **Step 1**（组件层）：新建 `pages/ProfilePage.tsx`，写 EditPanel + ImportExportPanel
2. **Step 2**（路由层）：`App.tsx` 加 lazy + Route
3. **Step 3**（导航层）：`SideMenu.tsx` 加 UserOutlined import + 第 4 组 items 追加
4. **Step 4**（验收）：tsc + oxlint + 手动跑 §4.1 验收清单

---

## 8. 预期效果

| 维度 | 现状 | 预期 |
|---|---|---|
| 个人偏好入口 | ❌ 侧边栏无入口，URL 也无路由 | ✅ 侧边栏第 4 组出现菜单 + `/profile` 路由 |
| 偏好可编辑 | ❌ 只能后端手动改 | ✅ 表单可视化编辑 + 字段动态增删 |
| 偏好可迁移 | ❌ 无法跨环境迁移 | ✅ 导出/导入 JSON |
| LLM 上下文注入 | ✅（后端已实现） | ✅（前端无关） |

---

## 9. 实测前置证据

| 引用点 | 文件:行 | 已验证 |
|---|---|---|
| 后端 `GET /api/profile` 端点 | `backend/app/api/routes.py:785-788` | ✅ |
| 后端 `PUT /api/profile` 端点 | routes.py:791-797 | ✅ |
| 后端 `POST /api/profile/import` 端点 | routes.py:800-806 | ✅ |
| 后端 `GET /api/profile/export` 端点 | routes.py:809-813 | ✅ |
| 前端 `getProfile` 函数 | `web/src/api/profile.ts:5` | ✅ |
| 前端 `putProfile` 函数 | `web/src/api/profile.ts:8-9` | ✅ |
| 前端 `exportProfile` 函数 | `web/src/api/profile.ts:12` | ✅ |
| 前端 `importProfile` 函数 | `web/src/api/profile.ts:15-16` | ✅ |
| `TradeProfile` 类型 | `web/src/types/index.ts` | ✅ |
| SideMenu 4 组结构 | `web/src/components/layout/SideMenu.tsx:18-65` | ✅（第 4 组「策略沉淀」已有 5 项：reviews/knowledge/agent-chat/rule-changes/experience，profile 插在 experience 前） |
| App.tsx 路由 | `web/src/App.tsx:34-50` | ✅（共 13 个 `<Route>`，profile 插在 experience 后、* 前） |
| 复用范式（Form + useQuery） | `pages/KnowledgePage.tsx:14-43` | ✅（AddPanel 已使用 `useQuery` + `useQueryClient` + `Form.useForm()` + `App.useApp()` 完整组合） |
