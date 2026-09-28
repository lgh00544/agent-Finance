# AI模拟_仓位放开_DSH执行指令（批 1 · v1.1）

> 目标文件路径：`D:\self\AI模拟_仓位放开_方案.md`（设计全文，动手前先读 §1-§4）
> 任务：把 AI 模拟账户（candidate_pool）的「固定 10% 首仓 → 每只恰好 1 手」改为「由 AI 决策层给目标仓位比例，执行器只做整手换算」。
> 只动 backend，前端不动。

## 一、元信息

- 仓库：`D:\self`
- 后端：`backend/`（Python）
- 测试环境变量：`DB_BACKEND=sqlite`（sqlite 快照库 `data/dev.db`）
- 验收依据：`AI模拟_仓位放开_方案.md` §4 / §6

## 二、改动（严格按清单，不扩范围）

1. `backend/app/services/paper_execution.py`
   - `POSITION_TARGET_MAX = 1.0`（仅「不超本金」物理边界）；保留 `CANDIDATE_POOL_INITIAL_ALLOCATION = 0.10` 作兜底。
   - 新增 `_normalize_target_allocation(value)`：None/非数/≤0 → None；`>1` ÷100；只夹 `(0, 1.0]`，**不设 5%~40% 策略上限**。
   - `:223 _candidate_pool_shares(account, price, code, allocation=None)`：allocation 优先，缺失回落兜底。
   - `_candidate_pool_lifecycle(..., target_allocation=None)`：add 分支用该比例；已用额度用尽（=1.0 或现金不足）则 hold（reason=`single_stock_target_reached`）。
   - `:496 run(...)` 增 `target_allocations: dict[str, float] | None = None`；解析优先级 ① 入参 ② `facts["target_allocations"]` ③ 仅 `live_paper` 调 `paper_analysis.size_position` ④ 兜底默认。`historical_replay` 禁止走 ③。
   - `:339 _payload` 的 `metadata_json` 增 `target_allocation` 与 `target_allocation_source`（`input|facts|llm|llm_unavailable|default`）。
2. `backend/app/services/paper_analysis.py`
   - 新增 `PaperSizeOutput`（`allocation_pct: float = Field(ge=0, le=100)`、`confidence`、`reasons`、`risk_note`）。
   - 新增 `size_position(candidate, score, plan, quote, context) -> dict`：复用 `_call(agent="size", ...)`、`ModelLevel.DEEP`、`ttl_seconds=86400`；失败返回 `{"status":"error","reason":"llm_unavailable"}`，**禁止用模型记忆猜数**。
3. `agent_prompts/position_size_prompt.py`（新增）：`SYSTEM_PROMPT` + `build_user_prompt(...)`。要求模型输出目标仓位比例（0~100，常规 5~40，**不设硬上限**）并给出依据；明确「仅影响模拟账本，不修改任何正式规则」。
4. `backend/app/api/routes.py`
   - `:1151 PaperRunBody` 增 `target_allocations: dict[str, float] = Field(default_factory=dict)`。
   - `:1324 paper_account_run` 把 `body.target_allocations` 透传给 `paper_execution.run`。
5. `backend/tests/test_paper_execution.py`
   - 保留 `:60-68`、`:254-262` 作「未传比例时兜底 10%」契约。
   - 新增 5 例：① 显式 `{"688901": 0.30}` → 3000 股；② 百分数 `30` → 3000 股；③ `0.90` → 9000 股（不夹）+ `150` → 现金收敛 9900 股；④ 回放 monkeypatch `paper_analysis.size_position` 断言 **0 次调用**；⑤ 额度用尽 hold（`single_stock_target_reached`）+ 未用尽加仓 900 股。
6. `backend/tests/test_paper_analysis.py`：新增 2 例（正常返回比例且冻结事实不含盘中价 / 候选缺失拒绝 + 模型失败 `llm_unavailable`）。

## 三、执行顺序

1. 读 `AI模拟_仓位放开_方案.md` §1-§4，核对 `paper_execution.py` 上述行号；
2. 按清单 1→4 改代码，5→6 补测试；
3. `DB_BACKEND=sqlite .venv/Scripts/python.exe -m pytest backend/tests/test_paper_execution.py backend/tests/test_paper_analysis.py -q`；
4. 提交门禁：干净副本 `git archive HEAD | tar -x` → `PYTHONPATH=<tmp>/backend python -c "import app.main; print('APP_MAIN_IMPORT_OK')"` + 同批 pytest 用例数比对；
5. 汇报：改动 `path:line` + passed/failed + 门禁实测输出。

## 四、红线

- 只动 backend；不碰前端 `web/src/`、不碰 Streamlit；
- 不写 `Holding`/`TradeRecord`；模拟账本与真实账本隔离不变；
- 涨跌停 / T+1 / 费用 / 滑点 / 现金约束**一律不放宽**；
- 100 股整手保留（交易所规则），不视为限制；
- LLM 只决定「比例」，成交价与费用全由代码算；
- 单票比例**不设代码上限**（C 拍板）；若日后重新引入上下限，视为交易规则 → 记 `review_log`，可回滚；
- 不自动 commit / push / 装依赖；连续 2 次失败停下报告；
- 超出本清单的改动一律不做，需先报告 sir。
