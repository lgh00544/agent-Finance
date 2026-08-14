# 每日候选池 Vue 3 试点 · 执行指令

> 生成：Lark（2026-08-13）
> 执行：Claude Code（sir 亲自驱动）
> 决策人：sir 拍板
> 定位：**B 档试点——用现代前端（Vue 3）重写「每日候选池」一个页面，验证技术路线后再决定是否全量迁移**
> 兼容性目标：移动端/浏览器访问、页面状态/交互弱

---

## 一、背景与目标

sir 认为现有 Streamlit 前端：①兼容性差（移动端/浏览器渲染、页面状态与交互弱）②时效性差（全量重跑模型）。已确认 A 档（Streamlit 内性能优化）先行，本指令为 **B 档试点**：在**不动现有 streamlit 目录**的前提下，新建 Vue 3 项目实现「每日候选池」页面，验证：

1. 技术路线是否可行（Vue 3 + Vite + Element Plus 对接现有 FastAPI 后端）
2. 交互与移动端体验是否显著优于 Streamlit
3. 试点页面首屏性能（目标 < 1s）

后端 API 已完整 REST 化，试点**零后端改动**。

---

## 二、技术栈与目录

新建独立目录 `d:\self\frontend-vue\`（与 streamlit/ 平级，试点阶段并行运行）：

| 项 | 选型 |
|---|---|
| 框架 | Vue 3（Composition API + `<script setup>`） |
| 构建 | Vite |
| 语言 | TypeScript |
| UI | Element Plus（深色主题，背景对齐 #0B0D13） |
| 状态 | Pinia |
| HTTP | Axios |
| 开发端口 | 5173（Vite dev server） |
| 后端代理 | **Vite proxy：`/api` → `http://localhost:8000`**（浏览器视角同源，**后端无需开 CORS**） |

标准脚手架：

```
frontend-vue/
├── index.html
├── package.json
├── vite.config.ts        # server.proxy: /api → http://localhost:8000
├── tsconfig.json
├── src/
│   ├── main.ts
│   ├── App.vue           # 顶部状态栏（时间/账户资产摘要）+ 页面主体
│   ├── styles/theme.css  # 深色主题变量（对齐现有配色）
│   ├── api/
│   │   ├── http.ts       # axios 实例（baseURL=/api，timeout GET 60s / POST 600s）
│   │   └── candidates.ts # 候选池相关接口封装
│   ├── stores/
│   │   └── candidates.ts # Pinia：日期/筛选/列表/统计/详情展开状态
│   ├── views/
│   │   └── CandidatesView.vue
│   └── components/
│       ├── DateSelector.vue     # 日期下拉
│       ├── StatCards.vue        # 可建仓统计卡
│       ├── FilterBar.vue        # 评级筛选 + 行业筛选 + 手动触发/批量对话按钮
│       ├── CandidateList.vue    # 候选列表（评级圆点/代码名称/副标题/时间/badge）
│       └── CandidateDetail.vue  # 详情抽屉/展开（维度归因/理由/技术面/量价/价位/风险/操作建议）
└── package.json 依赖：vue / vue-router(可选) / pinia / axios / element-plus / vite / @vitejs/plugin-vue / typescript
```

---

## 三、功能清单（MVP 优先）

### MVP（本阶段必须完成）

功能对齐 `streamlit/pages/1_每日候选池.py` 的只读展示与筛选：

1. **日期选择**：`GET /api/candidates/dates?limit=30`，下拉切换，默认最新
2. **可建仓统计卡**：`GET /api/candidates/tradeable?date=xxx&limit=200`，展示「今日可建仓标的」「可自动生成建仓计划的标的」两张卡（0 只也明确显示）
3. **候选列表**：`GET /api/candidates?date=xxx&limit=300`
   - 评级圆点（A 强烈推荐=B 建议关注=C 谨慎观察，映射规则：confidence_tier→A/B/C）+ 代码名称加粗
   - 副标题：标的类型 + 核心理由（reasons[0] 或 meso_view）
   - 生成时间、可建仓 badge（从 tradeable 视图取 is_tradeable/label）
   - 排序：可建仓置顶，A→B→C，组内按 rank
   - **同日同股去重**（created_at 最新覆盖）
4. **评级筛选**：全部候选 / 可建仓 A+B / 观察 C（segmented 控件或下拉）
5. **行业筛选**：URL query `?sector=xxx`，子串匹配 `detail.enriched.industry`；支持清除
6. **详情展开**：点击列表行展开完整研判——维度归因（dimensions 数组 + final_advice）、候选理由列表、技术面研判、量价与资金结论、关键价位、核心风险点、操作建议（标的类型/关注类型/参考建议）、三维验证（宏观/中观/微观）、风险初判
7. **分页懒加载**：首屏 20 条，滚动或按钮加载更多
8. **响应式**：移动端（375px）可正常浏览，列表与详情在窄屏自适应；PC 端深色卡片式布局

### 增强（第二里程碑，MVP 验收通过后再做）

9. 手动触发每日挖掘 / 单标的生成建仓方案（`POST /api/tasks/submit`，kind=daily_pipeline / position）+ 任务状态轮询展示
10. AI 研判留痕懒加载（`GET /api/traces?code=&date=` + `GET /api/traces/{id}`）
11. 批量验证对话面板（`POST /api/agent-chat/batch-ask` + `GET /api/tasks/{tid}` 轮询 + 调整方案展示与 `POST /api/agent-chat/batch-adjust/apply` 确认生效——**保持"人工确认才写入"语义**）

### 明确不做（试点范围外）

- 不迁移其他 12 个页面
- 不改造后端
- 不做登录/鉴权（本地单用户）

---

## 四、API 接口清单（已核实，直接使用）

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/candidates/dates?limit=30` | 候选日期列表 |
| GET | `/api/candidates?date=xxx&limit=300` | 候选列表（含 detail） |
| GET | `/api/candidates/tradeable?date=xxx&limit=200` | 可建仓判定视图 |
| POST | `/api/tasks/submit` | 提交任务（kind: daily_pipeline / position / batch_ask） |
| GET | `/api/tasks/{tid}` | 任务详情轮询 |
| GET | `/api/traces?code=&date=&limit=` | 推理留痕列表 |
| GET | `/api/traces/{trace_id}` | 留痕详情 |
| GET | `/api/agent-chat/history?agent=discover&limit=&message_type=batch` | 批量对话历史 |
| POST | `/api/agent-chat/batch-ask` | 提交批量验证 `{scope, codes, question, date}` |
| POST | `/api/agent-chat/batch-adjust/apply` | 确认生效 `{batch_id}` |

数据字段说明（从现有页面与 repo 确认）：
- 候选行：`stock_code / stock_name / trade_date / rank / created_at / reasons / risk_notice / detail`
- `detail.confidence_tier` ∈ {强烈推荐, 建议关注, 谨慎观察} → 展示评级 A/B/C
- `detail.stock_type`（标的类型）、`detail.dimensions`（维度数组：dim/score/verdict/advice）、`detail.final_advice`（综合评估）、`detail.tech_view / volume_analysis / price_levels / risks / focus_type / position_hint / macro_view / meso_view / micro_view`
- `detail.enriched.industry`（行业字段，用于行业筛选）
- tradeable items：`stock_code / is_tradeable / label`（label ∈ 可建仓/建议关注/观察/未判定）

---

## 五、工程细节与约束

1. **零后端改动**：试点页面通过 Vite proxy 访问后端，`/api` 前缀代理到 8000，浏览器端不做跨域，后端不加 CORS 中间件
2. **不删改现有 streamlit 目录**：试点并行运行，两套前端共存
3. **深色主题对齐**：背景 #0B0D13、卡片 #141824、主色 #3B82F6、文字 #E5E7EB，与现有 Streamlit 视觉一致
4. **错误处理**：接口失败显示分类错误提示 + 重试按钮（对齐现有页面体验）；无数据时空态明确
5. **加载态**：列表/详情有 loading 反馈；详情懒加载（未点击不请求）
6. **类型安全**：为候选/详情/tradeable/task 定义 TS interface（对齐后端 pydantic 字段名，不做二次改名）
7. **状态管理**：Pinia 管理日期/筛选/列表/详情展开/任务状态，URL query 承载日期与行业（可分享/可刷新保持）
8. 开发运行：`cd frontend-vue && npm install && npm run dev`（5173）
9. 交付：前端代码 + 启动说明 + 与现有页面功能对比清单 + 移动端截图验证

---

## 六、验收标准（全部通过才算完成）

- [ ] `npm run dev` 启动无报错，5173 端口可访问
- [ ] 后端运行状态下（backend/dev_run.py），页面能拉到真实候选数据
- [ ] 功能对齐：日期切换/评级筛选/行业筛选/详情展开/统计卡，行为与现有 Streamlit 页面一致
- [ ] 同日同股去重、可建仓置顶排序正确
- [ ] 首屏加载 < 1s（Network 面板确认，仅少量请求）
- [ ] 移动端 375px 宽度布局正常（可滚动/可展开详情/无横向溢出）
- [ ] 接口失败时显示分类错误 + 重试，不白屏
- [ ] 深色主题与现有系统视觉一致

---

## 七、运行说明（交付给 sir）

```bash
# 后端（如未运行）
cd /d/self && SYNC_ON_START=false ./.venv/Scripts/python.exe backend/scripts/dev_run.py

# 试点前端
cd /d/self/frontend-vue
npm install
npm run dev   # http://localhost:5173
```

现有 Streamlit 不受影响（8501 端口照常）。

---

*Lark 制定。B 档试点：一个页面验证 Vue 3 技术路线，通过后再评估全量迁移。*
