# 候选因子·改为查询 pending 列表（真因修复）_执行指令

## 背景与真因（已核实）
sir 实测：点「AI 提议候选因子」提示已生成 5 个，但列表显示「暂无数据」，不知道生成了什么。

核实结论：
- 后端 `factor_candidate.py:35-53 propose()` **本来就返回完整字段**（`[_row(row) for row in rows]`），数据已落库为 pending
- 前端 `ReviewsPage.tsx:67-110 FactorCandidates` 用 `useState` 本地 state，**从不查询后端** → 切 Tab / 刷新 / 组件重挂载即丢空 → 呈现「暂无数据」
- 前端 `web/src/api/factors.ts:38 getPendingCandidates()` 指向 `GET /factor-candidates/pending`，但**后端该路由不存在**（routes.py 只有 `POST /factor-candidates/propose`）→ 历史候选无法拉取
- 后端 service 已有现成读取函数 `factor_candidate.py:56-64 get_pending_for_sir(limit)`，只差路由暴露

## 改动点

### 1. 后端补只读路由（backend/app/api/routes.py，紧邻 line 666 的 propose 路由）
新增：
```python
@router.get("/factor-candidates/pending")
def factor_candidates_pending(limit: int = 50):
    """待人工拍板的候选因子列表；纯读，不改状态。"""
    from app.services.factor_candidate import get_pending_for_sir
    return get_pending_for_sir(limit)
```
**禁止**调用 `require_write_access()`（只读接口）。

### 2. 前端改为查询式（web/src/pages/ReviewsPage.tsx:67-110）
- import 增加 `getPendingCandidates`（来自 `@/api/factors`）
- 组件内：
  - 删除 `const [rows, setRows] = useState<FactorCandidate[]>([])`
  - 新增 `const qc = useQueryClient()`
  - 新增 `const { data: rows, isLoading } = useQuery({ queryKey: ['factor-candidates-pending'], queryFn: () => getPendingCandidates() })`
  - mutation `onSuccess` 改为：`message.success(\`已生成 ${data.length} 个候选因子\`)` + `qc.invalidateQueries({ queryKey: ['factor-candidates-pending'] })`（**不再 setRows**）
- Table：
  - `dataSource={rows ?? []}`
  - `loading={isLoading}`
  - `rowKey={(r) => String(r.id ?? r.candidate_id)}`（防 candidate_id 异常导致 key 冲突）
  - 列保持现有（ID/名称/分类/假设/状态/操作），详情 Drawer（line 90-107）保留不动
- 空态文案改为：「暂无待审核候选因子；点击上方按钮提议，或在下方状态筛选查看已启用因子」（仅当确实为空时）

## 红线
1. **不动** `propose()` / `validate()` / `enable()` / `get_pending_for_sir()` 的任何逻辑（service 层零改动）
2. **不动** `FactorCandidate` 表结构与模型
3. **不动**因子生成、IC 计算、评分、规则阈值
4. 新增路由**必须只读**，不得写库、不得改 status
5. 前端仅改 `FactorCandidates` 组件，不动 ReviewsPage 其他 Tab
6. 改动 ≤ 30 行，不新增文件

## 验收
1. `GET /api/factor-candidates/pending?limit=50` 返回 200 + 数组（含此前已生成的 fc11–fc20 等 pending 行，字段完整：candidate_id/name/category/hypothesis/formula/status/...）
2. 打开「候选因子」Tab **立即**看到历史候选（无需先点生成）
3. 点「AI 提议候选因子」→ 列表自动刷新并包含新增的 5 条
4. 切到其他 Tab 再切回 / 刷新浏览器 → 列表仍在
5. 点「详情」Drawer 正常（分类/假设/状态/公式/数据需求/预期边/风险说明/验证结果 JSON）
6. `tsc -b --force` EXIT=0；`pytest tests/test_factor_candidate.py` 全绿（不得因本次改动变红）
