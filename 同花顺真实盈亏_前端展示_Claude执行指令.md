# 同花顺真实账户今日盈亏 · 前端展示 — Claude Code 执行指令

## 0 元信息
- 生成者：Lark / 决策人：sir / 执行者：Claude Code
- 背景：后端同花顺真实盈亏（ths_pnl，commit `ea2251a`）**全链路已接线、默认关 `THS_PNL_ENABLE=false`**，但前端**无展示**——本批在「总览」补一张真实今日盈亏卡 + 接线验收。
- 需求方案详见 `D:\self\同花顺账户接入_方案.md` §4.3（P1 前端）与 §5 R1（Cookie 过期）。

## 一 目标
在 React **OverviewPage 总览**（市况速览区）加一张「今日真实盈亏」卡，消费 `GET /api/account/pnl`，三态诚实展示：
- `configured:false`（未开启/未配 Cookie）→ 灰态「未接入 · 同花顺真实盈亏未启用」，**不假装有数据**。
- `configured:true` → 显示 `snapshot.pnl_yk`（盈亏额 ¥）+ `pnl_pct`（盈亏%）+ `sh_pct`（上证对比）+ `updated_at`。
- `snapshot.token_expired=true` 或 `error` 非空 → **可操作提示**，不掩盖。

**不做**：不新建独立页面；后端/调度/service/repo/config 一律不动；不做任何交易动作；仅展示。

## 二 架构约束
- 只动 `web/src/`：`web/src/api/account.ts` 增 `accountPnl()` + `web/src/pages/OverviewPage.tsx` 市况速览 grid 加一个格子；可选 `web/src/types/index.ts` 补类型。后端零改动。
- 复用现有 `get` client、antd `Card/Tag/Text/Space`、涨红跌绿语义（*A 股红涨绿跌，非交易意义*）。
- 默认关的降级路径是**必须**：没配 Cookie 时页面不能报错/白屏。

## 三 规则
**API 契约（只消费）：**
- `GET /api/account/pnl` → 未开启 `{"configured": false}`；已开启 `{"configured": true, "snapshot": {pnl_yk, pnl_pct, sh_pct?, chart_data, updated_at, error?, token_expired?}}`（字段可空）。

**展示（OverviewPage.tsx 市况速览区，Card title="市况速览" 的 grid，line 184，在「三大指数」cell 后加一个 cell）：**
- 标题 `今日盈亏(同花顺)`；有值 → 金额 `+¥x.xx` / 百分比 `+x.xx%`，`pnl_yk>=0` 红色、`<0` 绿色；无值 → `—`。
- 上证：若 `sh_pct != null`，同格下方显示 `上证 +x%`（涨红跌绿 Tag）。
- **过期提示（R1 落地）**：`token_expired=true` → 显示橙色 Tag「同花顺 Cookie 已过期，请到 DSH 插件重新登录」。
- **数据新旧**：`updated_at` 显示在格底（`slice(5,19)`）；若 `snapshot.updated_at` 距当前 > 10 分钟，加 `text type="secondary"` 备注「(可能过期)」。
- `error` 非空 → 格底红字显示 error 摘要（不崩）。

**诚实降级：** `configured:false` → 灰态「未接入」；null/缺字段 → `—`；`token_expired/error` → 如实展示；**绝不出假正数**。

## 四 执行顺序
1. `grep` 定位 `OverviewPage.tsx` 市况速览 grid（约 :184-215）与 `api/account.ts`；`get` 签名在 `api/client.ts`。
2. `api/account.ts`：`export const accountPnl = (): Promise<AccountPnl> => get('/account/pnl')`；`AccountPnl` 类型放 `types/index.ts`（`configured: boolean; snapshot?: {...}`）。
3. `OverviewPage.tsx`：import `accountPnl`；`const { data: pnl } = useQuery({ queryKey:['account-pnl'], queryFn: accountPnl, refetchInterval: 60_000 })`。
4. 市况速览 grid 加「今日盈亏(同花顺)」cell，按 §三 三态渲染。
5. `npm run build`（或 `tsc -b`）零错。

## 五 验证清单
- [ ] `tsc -b` / `npm run build` 零错；未用 import/variable 已 grep 核对
- [ ] `THS_PNL_ENABLE=false`（默认）→ 页面「未接入」灰态，不报错/白屏
- [ ] `configured:true` 有值 → 显示真实 ¥/-%，涨红跌绿，无假数
- [ ] `token_expired:true` → 出现「去 DSH 插件重新登录」橙色提示
- [ ] `snapshot` 缺字段 / null → `—` 占位不崩
- [ ] `git diff` 仅 `web/src/`（backend 零改动），≤150 行，未引新库

## 六 红线
1. **后端零改动**——ths_pnl service/scheduler/repo/config/routes 一律不动（已接线）。
2. 只动 `web/src/` ≤150 行；不引新库（用现有 antd/Card）。
3. **诚实原则绝不伪造**：未配置/错误/缺数据一律如实展示，伪造数据违规。
4. 全默认关回归：不改 `THS_PNL_ENABLE` 默认值，只做展示层。
5. 省 token：只 grep 定位、不 read 全量；docstring ≤3 行；报告 ≤10 行；超 150 行停。
