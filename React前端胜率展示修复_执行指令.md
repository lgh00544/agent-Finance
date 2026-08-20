# React 前端胜率展示修复 · Claude Code 执行指令

> **作者**：Lark
> **日期**：2026-08-20
> **改动范围**：仅 2 个 React 前端文件 + 1 个类型注释
> **依据**：后端 `track_verify.py:127` 已返回 0-100 百分制 `win_rate`，React 层又乘 100 导致显示 4400.0%

---

## 1. 背景

 sir 在 React 新前端（`http://localhost:5173` 或 `http://localhost:8000`）的「每日候选池」页看到：

- **近期选股胜率：4400.0%**
- **平均涨幅：+0.58%**

实测后端 `/api/track/verify/stats?period=t5` 返回：

```json
{
  "n": 25,
  "wins": 11,
  "win_rate": 44.0,
  "avg_pct": 0.58
}
```

后端 `backend/app/services/track_verify.py:127`：

```python
return {"n": n, "wins": wins, "win_rate": round(wins / n * 100, 1), ...}
```

即 `win_rate` 已经是 **0-100 百分制数值**（44.0 表示 44.0%）。

但 React 前端两处代码把 `win_rate` 当成 0-1 小数，再次乘以 100：

- `web/src/pages/CandidatesPage.tsx:572`：`` `${(wr * 100).toFixed(1)}%` ``
- `web/src/pages/ReviewsPage.tsx:132`：`` `${(wr * 100).toFixed(1)}%` ``

44.0 × 100 = **4400.0%**，与截图一致。

---

## 2. 红线（强制遵守）

| 红线 | 验证 |
|---|---|
| **只改 React 展示层** | `backend/` 零改动 |
| **不动 Streamlit 旧前端** | `streamlit/` 零改动 |
| **不动数据计算/统计逻辑** | `track_verify.py` / `repo.py` 零改动 |
| **不动交易规则/研判标准** | `agent_prompts/` / `agents/` 零改动 |
| **改动可回滚** | 改前 `cp CandidatesPage.tsx CandidatesPage.tsx.bak.winrate` 等 |
| **不引入新依赖** | 仅用现有 `StatCard` 组件 |

---

## 3. 详细规格

### 3.1 备份

```bash
cp web/src/pages/CandidatesPage.tsx web/src/pages/CandidatesPage.tsx.bak.winrate
cp web/src/pages/ReviewsPage.tsx web/src/pages/ReviewsPage.tsx.bak.winrate
```

### 3.2 修改 `web/src/pages/CandidatesPage.tsx`

**原代码**（line 571-574 附近）：

```tsx
<StatCard label="近期选股胜率"
  value={wr != null ? `${(wr * 100).toFixed(1)}%` : '无数据'}
  tone={wr != null ? (wr >= 0.5 ? 'ok' : wr < 0.4 ? 'err' : 'warn') : 'mute'}
  sub={`盈利 ${tvStats?.wins ?? 0} 笔 / 共 ${tvN} 笔（T+5 已到期）`} />
```

**改为**：

```tsx
<StatCard label="近期选股胜率"
  value={wr != null ? `${wr.toFixed(1)}%` : '无数据'}
  tone={wr != null ? (wr >= 50 ? 'ok' : wr < 40 ? 'err' : 'warn') : 'mute'}
  sub={`盈利 ${tvStats?.wins ?? 0} 笔 / 共 ${tvN} 笔（T+5 已到期）`} />
```

**改动点**：
1. 删除 `* 100`：`` `${wr.toFixed(1)}%` ``
2. tone 阈值同步改为百分制：`wr >= 50` / `wr < 40`

### 3.3 修改 `web/src/pages/ReviewsPage.tsx`

**原代码**（line 132 附近）：

```tsx
<StatCard label="胜率" value={wr != null ? `${(wr * 100).toFixed(1)}%` : '无数据'} />
```

**改为**：

```tsx
<StatCard label="胜率" value={wr != null ? `${wr.toFixed(1)}%` : '无数据'} />
```

### 3.4 类型注释防踩坑（`web/src/types/index.ts`）

在 `TrackVerifyStats` 接口的 `win_rate` 字段上加 JSDoc 注释，避免未来再次误乘 100：

**原**：

```ts
export interface TrackVerifyStats {
  n?: number
  wins?: number
  losses?: number
  win_rate?: number | null
  avg_pct?: number | null
  ...
}
```

**改为**：

```ts
export interface TrackVerifyStats {
  n?: number
  wins?: number
  losses?: number
  /** 胜率，单位：0-100 的百分制数值（如 44.0 表示 44.0%）。前端展示时不要再乘以 100。 */
  win_rate?: number | null
  avg_pct?: number | null
  ...
}
```

### 3.5 顺手检查 `HotMoneyProfile.win_rate_5d` 是否同类问题

- `web/src/pages/HotMoneyPage.tsx:34` 仅定义列 `dataIndex: 'win_rate_5d'`，未自定义渲染函数
- 若表格实际渲染也显示 `4400%`，说明后端 `win_rate_5d` 同样是 0-100 百分制、Antd Table 默认直接显示原始值——通常不会乘 100
- **本次不动 HotMoneyPage**，如 sir 后续报同样问题再处理

---

## 4. 验证清单

### 4.1 编译

- [ ] `cd web && npm run build` 0 error
- [ ] `cd web && npx tsc --noEmit` 0 error

### 4.2 浏览器验证

- [ ] 重启 dev server / 强制刷新 `Ctrl+Shift+R`
- [ ] 候选池页「近期选股胜率」显示 **44.0%**（而非 4400.0%）
- [ ] 候选池页 tone 颜色正确：44.0% → `warn`（40-50 区间）；≥50 → `ok`；<40 → `err`
- [ ] 交易复盘页「胜率」显示 **44.0%**（而非 4400.0%）
- [ ] 平均涨幅仍显示 **+0.58%**（本次未动，作为参照）

### 4.3 回归

- [ ] 候选池页其他 StatCard（今日可建仓标的 / 可自动生成建仓计划 / 平均涨幅）数字不变
- [ ] 候选池列表渲染、筛选、排序、分页功能正常
- [ ] 交易复盘页「选股效果验证」追踪列表、统计卡、趋势图正常
- [ ] 后端 `/api/track/verify/stats` 返回值不变（仍为 44.0）

### 4.4 红线

- [ ] `git diff --stat` 仅 `web/src/pages/CandidatesPage.tsx`、`web/src/pages/ReviewsPage.tsx`、`web/src/types/index.ts` 3 个文件
- [ ] `backend/` 零改动
- [ ] `streamlit/` 零改动

---

## 5. 回滚方案

| 失败点 | 回滚 |
|---|---|
| 显示异常 | `mv CandidatesPage.tsx.bak.winrate CandidatesPage.tsx` |
| Reviews 页异常 | `mv ReviewsPage.tsx.bak.winrate ReviewsPage.tsx` |
| 整体失败 | `git checkout HEAD -- web/src/pages/CandidatesPage.tsx web/src/pages/ReviewsPage.tsx web/src/types/index.ts` |

---

## 6. 原因总结（可复制给工程师同步）

> React 新前端「每日候选池」和「交易复盘」两页把后端返回的 0-100 百分制 `win_rate` 当成 0-1 小数再次乘以 100，导致 44.0% 显示为 4400.0%。后端 `track_verify.py` 返回正确，只需改 React 展示层：删除 `* 100`、同步 tone 阈值为百分制（≥50 ok / <40 err / 中间 warn），并在 `types/index.ts` 加注释防未来踩坑。改动 3 文件，不动后端/Streamlit/交易规则。
