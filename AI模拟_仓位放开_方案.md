# AI模拟_仓位放开_方案（v1.1 · 2026-09-28）

> 触发：sir 问「AI 模拟是不是限制每只标的只能买 100 股？别有这个限制，就是要让它探索可能性的」。
> 结论：**不存在「每只只能买 100 股」的硬编码**；100 股是「固定比例首仓 + 100 股整手向下取整 + 账户资金偏小」三者的合成结果。
>
> **v1.1 修订（2026-09-28 sir 拍板 C）**：取消 5%~40% 代码上下限，单票目标比例只受 100 股整手、可用现金与费用约束；下文 §2 / §3 / §4 / §6 已按此更新。

## 1. 现状与证据

| 位置 | 内容 | 影响 |
|---|---|---|
| `backend/app/services/paper_execution.py:20` | `LOT_SIZE = 100` | A 股最小交易单位，保留 |
| `:37` | `CANDIDATE_POOL_INITIAL_ALLOCATION = 0.10` | 候选池账户首仓固定 = 初始资金 10% |
| `:38-39` | `ADD_ALLOCATION = 0.10` / `MAX_ALLOCATION = 0.20` | 加仓固定 10%，单票上限 20% |
| `:204-220` | `_candidate_pool_allocation_shares` 整手向下取整 + 滑点/费用/现金收敛 | 不足 1 手即 0 |
| `:223-225` | `_candidate_pool_shares` 首仓入口 | 无任何 AI 参与 |
| `:279-322` | `_candidate_pool_lifecycle` 加/减仓 | 加仓同样固定 10% |
| `:667-671` | 买入分支按 variant 选 `_candidate_pool_shares` | — |

实测（`data/dev.db`，账户 30001「候选池研究」，`strategy_variant=candidate_pool`）：
`initial_cash=33,960.64`，持仓 `600900` 100 股（均价 28.64）、`600938` 100 股（均价 33.92）。
→ 10% = 3,396 元；28.64 / 33.92 元都只够 1 手 → **每只恰好 100 股**。

既有测试把该行为锁死：`backend/tests/test_paper_execution.py:60-68`（33,960.64 + 34.4 元 → 100 股）、`:254-262`（100,000 + 10 元 → 1000 股）。

## 2. 目标（sir 已选：由 AI 决策层给每只标的目标仓位比例）

- 仓位比例改由 **AI 决策层**产出，执行器只做「比例 → 整手 → 滑点/费用/现金」确定性换算；
- **不设单票代码上限**（C 拍板）：可买量只由「100 股整手 + 可用现金 + 费用」决定；`POSITION_TARGET_MAX=1.0` 只是「不超本金」的物理边界，可在换算前被现金进一步收敛；
- 「100 股整手」是 A 股交易所规则，保留，不视为限制；
- 历史回放保持零 LLM（未来数据隔离），只用显式传入或兜底默认。

## 3. 数据流

```
AI 决策层 ──target_allocations{code: 比例}──┐
                                          ├─▶ paper_execution.run ─▶ 整手/现金/费用 ─▶ paper_execution 落账
显式 API / 回放调用 ───────────────────────┘        (metadata 记录 target_allocation，可审计可回滚)
                                          └─▶ live_paper 且未提供时，调用 paper_analysis.size_position（新 LLM 适配器）
```

解析优先级：① 入参 `target_allocations` → ② `facts["target_allocations"]` → ③ live_paper 下 AI 适配器 `paper_analysis.size_position` → ④ 兜底默认 10%（保留，仅兜底）。
归一化：`>1` 视为百分数（÷100）；上限 1.0 为「不超本金」物理边界；非数/≤0 → 视同缺失。
回放：`historical_replay` **禁止**走 ③，仅 ①②④。

## 4. 改动清单（只动 backend）

| # | 文件 | 改动 |
|---|---|---|
| 1 | `backend/app/services/paper_execution.py` | 新增 `POSITION_TARGET_MAX=1.0`（物理边界，非策略上限）；新增 `_normalize_target_allocation`（不再夹 5%~40%）；`_candidate_pool_shares` 增 `allocation` 参数；`_candidate_pool_lifecycle` 加仓用同一比例、仅额度用尽时 hold（`single_stock_target_reached`）；`run()` 增 `target_allocations`；metadata 记 `target_allocation`/`target_allocation_source` |
| 2 | `backend/app/services/paper_analysis.py` | 新增 `PaperSizeOutput`（`allocation_pct`/`confidence`/`reasons`/`risk_note`）与 `size_position(...)`（复用 `_call`，agent=`paper_size`，DEEP，缓存 86400s；失败返回 `status=error`，**不猜数**） |
| 3 | `agent_prompts/position_size_prompt.py`（新增） | `SYSTEM_PROMPT` + `build_user_prompt`；输出目标仓位比例（0~100，常规 5~40，**不设硬上限**），必须给依据，仅模拟不改规则 |
| 4 | `backend/app/api/routes.py` | `PaperRunBody`(:1151) 增 `target_allocations: dict[str, float]`；`/paper/accounts/{id}/run`(:1324) 透传 |
| 5 | `backend/tests/test_paper_execution.py` | 保留 :60-68 / :254-262 作为「未传比例时兜底 10%」契约；新增 5 例：显式 0.30 → 3000 股、百分数 30 → 3000 股、0.90 → 9000 股（不夹）+ 150% → 现金收敛 9900 股、回放断言 `size_position` 0 次调用、额度用尽即 hold + 未用尽加仓 900 股 |
| 6 | `backend/tests/test_paper_analysis.py` | 新增 2 例：`size_position` 正常返回比例（且冻结事实不含盘中价）/ 候选缺失拒绝 + 模型失败 `llm_unavailable` |

## 5. 成本控制（LLM 只在新候选、只在 live）

- 仅在 `live_paper` + 已通过全部买入闸门 + 该 code 未持仓时调用；
- 复用 15 分钟研究上下文（`paper_monitor._CONTEXT_MINUTES`）与 `call_llm_cached`，每 code 每 15 分钟至多 1 次；
- 回放零调用；失败兜底默认比例并标 `target_allocation_source=llm_unavailable`。

## 6. 验收

1. 单测：`test_paper_execution.py`、`test_paper_analysis.py` 全绿；
2. 目标账户口径：显式 `allocation=0.40`、600938@33.9 → `floor(33960.64*0.40/33.9/100)*100 = 400` 股；`allocation=1.0`、10 万本金 @10 元 → 由现金/费用收敛到 **9900** 股（非 10000）；
3. 兜底：不传 allocation 且非 live → 仍 10%，保证既有回放不变；
4. 门禁（AGENTS.md 提交门禁）：干净副本 `PYTHONPATH=backend python -c "import app.main"` 打印 `APP_MAIN_IMPORT_OK`；干净副本跑同一批 pytest 用例数与工作区一致。

## 7. 红线

- 只动 backend；前端展示（如需）另批；
- 不写 `Holding`/`TradeRecord`；`cannot_do` 不变；
- 涨跌停 / T+1 / 费用 / 滑点约束**不放宽**；
- 交易规则表 `auto-merge` 不动；比例上下限若认定为规则 → 记 `review_log` 可回滚；
- LLM 只做「比例」判断，不做成交价计算。
