# 🔴 第一硬规则：目标不打折扣地落地（2026-09-16 sir 拍板，优先级高于本文件其他一切条目）

> sir 原话：「目标要不打折扣的落地，这是硬规则，要不然哪里都讲究一点，最终肯定不达标。」

- **功能范围 / 数据正确性 / 验收标准一律不打折扣**——指令列了几项就是几项，一条不砍
- **禁止「哪里都讲究一点」**：少写一个分支、跳过一项验收、把"完整实现"退成"先跑通"——每次让一小步，累积起来整体必不达标
- **遇到阻碍换方法，不降目标**：断流 → 分段落盘 + 断点续跑；任务过大 → 分批交付，但**每批标准与原目标完全一致**（"切"≠"减"）
- **「先跑通再说」是降标准**：跑通 ≠ 验收通过。跑通后仍须按原验收清单逐条勾完
- **省 token 只省表达形式**（重复、复述、冗余、全量读文件），**不省功能、验收项、数据准确性、边界处理**；冲突时以目标为先
- **交付前自检三问**：①目标里的功能砍了没？②验收清单条目少了没？③边界/异常/缺失数据的处理简化了没？——任一为"是"即返工

---

# 项目执行纪律（省 token 版，2026-08-24 起生效）

对每次任务的执行行为约束，与执行指令配合使用：

1. **精准读文件**：只读指令指定的 `path:line` 附近（±30 行），不整读大文件；上下文不够再逐步扩大。
2. **引用文档按节定位**：遇到「参见 XXX_方案.md §N」→ 先 `grep -n "^#" 该文件` 定位节起始行，再按 offset/limit 只读该节，禁止整读。
3. **测试最小化**：只跑与本次改动直接相关的测试文件；全量回归仅当指令明确要求时执行。
4. **不重复读**：同一任务内已读过的文件不二次整读。
5. **grep 优先**：定位标识符/字段/调用方一律先 grep，不通读目录。
6. **汇报精简**：只报 改动文件+行号 / 测试 passed·failed 数 / 红线逐条核对结论；不贴大段代码，不写过程叙述。
7. **方案/提示词分工**：详细内容一律沉淀 `{主题}_方案.md`（≤600 行），单份执行指令 ≤250 行（简单任务 ≤80 行）；提示词内用「参见 §X」引用方案已写内容，禁止重抄。单次提示词批次数 ≤3，批次内 review→改 循环 ≤2 轮，超出停下报告 sir。
8. **每任务独立 opencode 会话**：独立任务（不同批次/不同 issue/跨工作日）必开新会话；跨任务状态靠 `D:\self\.workbuddy\memory\` 下的 daily log / MEMORY.md，不靠对话历史。单会话输入 >200K 或 >30 轮 → 收尾 commit，新会话继续。

---

# 提交门禁（每次 commit 前强制，2026-09-20 起）

> 背景：同类「提交清单遗漏」已连续发生 **5 次**，其中依赖遗漏 3 次（`app/factors/`、`factor_registry.py`、`config.py` 致 HEAD import 崩）、
> 测试遗漏 2 次（`test_financial_normalization.py`、`test_datasource_stability.py` 致 HEAD 零回归守卫）。
> 光靠「人工列清单」无效 —— **必须用机制验证**。

**commit 前逐条执行，任一不过即停：**

1. **列清单不得靠关键词 grep**。「改了哪些文件」必须按**依赖闭包**推：改动的模块 + 它 import 的模块 + **配套测试文件**。
2. **干净副本导入验证**（挡依赖遗漏）：
   ```
   mkdir -p <临时目录> && git archive HEAD | tar -x -C <临时目录>
   cd <临时目录> && PYTHONPATH=<临时目录>/backend python -c "import app.main; print('APP_MAIN_IMPORT_OK')"
   ```
   必须打印 `APP_MAIN_IMPORT_OK`。⚠️ 在工作区跑 import 会**假绿**（未跟踪文件就在磁盘上），不算数。
3. **干净副本测试数验证**（挡测试遗漏 —— 第 2 条验证不了这个，测试不参与 import）：
   在干净副本上跑与工作区**同一批** pytest 文件，**用例数必须与工作区一致**。
   例：工作区 `test_datasource_stability` 20 例，HEAD 版必须也是 20 例；若 HEAD 只有 16 例 → **必有 4 个测试没提交**。
4. 验证完删除临时目录。
5. 报告里须并列：`git show --name-only HEAD` 的文件数 + 上述两项门禁的实测输出。

**为什么这两条是硬门禁**：5 次同类问题中，第 2 条能挡住前 3 次，第 3 条能挡住后 2 次 —— 两条合起来覆盖全部 5 次。

---

## 项目改动边界（铁律，动手前先核对）

1. **前端只改 React `web/src/`，不动 Streamlit `streamlit/pages/`**。例外仅三种：①后端 API 变更致旧版报错阻塞 ②sir 显式点名 ③React 侧功能尚未迁移。**后端 / 数据 / Agent / 交易规则改动只动后端**，两端共同消费，不重复实现。
2. **Agent 解耦**：新增或修改能力只动各 Agent 的 `collect` 段，**不动** `agent_call` / `push_alert_node`。
3. **自文件落盘**：提示词 / 方案 / 执行指令 / 审核结论 / 工单 / 风险清单 → 默认写 `D:\self\{主题}_{版本}_{文档类型}.md`，**不写桌面**（桌面仅保留历史镜像）。
4. **交易规则与研判标准表**：`auto-merge` **永不修改**；任何规则改动必须经 `review_log` 可回滚。

---

## 高频陷阱（写代码 / 审核前必查）

以下均为本项目实际踩过的坑，改动前先逐条对照：

| # | 陷阱 | 正确做法 |
|---|---|---|
| 1 | **win_rate 口径不一致** | `track_verify._group_stats` 返回 **0-100 百分制**，`_calc_stats` 返回 **0-1 小数**。展示层必须显式归一化后再渲染（"4400%" 显示异常的根因）。 |
| 2 | **前端默认拉全表** | 用 `date` state 作查询条件时，必须 `useEffect(() => { if (!date && dates?.length) setDate(dates[0]) }, [dates, date])` 且 `enabled: !!date`；否则 `<Select value={date ?? dates?.[0]}>` 是非受控显示，queryFn 会传 `undefined` 拉全表。参考 `CandidatesPage.tsx`。 |
| 3 | **字段名猜错** | `repo.list_candidate_tradeable` 的字段是 `tier` / `price_zone` / `label` / `block_reason`，**不是** `grade` / `reason` / `potential_flag`。 |
| 4 | **类型文件找错** | `TradeProfile` 在 `web/src/types/index.ts`（约 294 行）；**`web/src/types/trade.ts` 不存在**。 |
| 5 | **dashboard 聚合调错接口** | 禁止调 `tradeable_view()`（内部 `ensure_if_missing` 会触发约 900 次 DB 查询），改用 `repo.list_candidate_tradeable(trade_date, limit=50)`。 |
| 6 | **tsc 通过 ≠ 改动落地** | 未使用的 import / 函数 tsc 不报警，`EXIT=0` 不代表生效；必须 grep 统计关键标识出现次数核对。 |
| 7 | **useEffect 死循环** | 不要在 render 阶段直接 `form.setFieldsValue`。 |
| 8 | **注释与实现不符** | `structured.py` 中「LIGHT = Discover 初筛」注释**是错的**，Discover 3 处调用全为 DEEP，**以代码为准**。 |
| 9 | **断路器未生效** | `fetch_industry_spot` 必须传 `kind="snapshot"` 才走断路器。 |
| 10 | **WebFetch 失效** | 改用 `request` 直调 akshare；`market_hours.snapshot_allowed()` 是交易日闸门。 |
| 11 | **AppTest 22 failed** | 属环境性内存压力，与代码改动无关，不要据此返工。 |

---

## 本机环境（沙箱特有，起服务 / 排障前先看）

- **shell PATH 可能被清空**：`grep` / `tr` / `head` / `git` 会 `command not found`。每条 Bash 调用前先 export：
```
export PATH="/c/Users/57388/.workbuddy/binaries/PortableGit/versions/1.2.0/cmd:/c/Users/57388/.workbuddy/binaries/PortableGit/versions/1.2.0/mingw64/bin:/c/Users/57388/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin:/c/Users/57388/.workbuddy/binaries/node/versions/22.22.2-3:/c/Windows/system32:/c/Windows:/c/Windows/System32/Wbem"
```
  要点：`git.exe` 在 `cmd/` 与 `mingw64/bin/`（**不在 `bin/`**）。⚠️ 查仓库状态**不要加 `2>&1`**——`git: command not found` 会被 `wc -l` 算成 1 行，看着像"有 1 处变更"。
- **后端启动约 6.5 分钟，期间端口不监听 ≠ 挂了**：`init_db()` 迁移 → `SYNC_ON_START` 云同步（3.7 万行）→ 重型 import + APScheduler + 飞书桥 → 才 bind `:8000`。**判定失败前至少等 7 分钟**；前端约 6s。
- **"failed" 通知 ≠ 服务真挂**：先 `netstat -ano | findstr ":8000 :5173"` + `curl /api/health`，端口在监听且 health ok 就不要动它。
- **前端启动必带两个环境变量**：`CODEBUDDY_SAFE_DELETE_ENABLED=0 CODEBUDDY_SAFE_DELETE_SANDBOX=0`，否则 safe-delete 拦截 vite 删缓存直接崩。项目用 **pnpm**；`web/start_frontend_hidden.bat` 的 `VITE_API_PROXY` 默认 8100，而 `vite.config.ts` 默认 8000，**按该脚本启动须显式传 8000**。
- **Vite 报 `os error 5 拒绝访问`** → 原样重试一次即可，不要去删 `node_modules`，也不要改 vite 配置。

---

## 工具默认行为守则（2026-09-14 起，所有 agent 默认遵守，不再需要任务前缀重写）

> 背景：sir 用 Codex + XMirai 中转站时被"循环重连/钻牛角尖"烧过 token。这套守则解决三件事——**保留能力、约束行为、熔断靠预算**。

### 一、必须保留的能力（不阉割）

- 模型默认全量版（`gpt-5` / `claude-sonnet-4.5` / `DeepSeek-V3`），**不切 mini**——mini 返工率翻倍，反而更烧 token
- `max_tokens ≥ 8000`，给够思考/分析空间，**不卡 4K**
- 工具访问（文件读写、Bash、grep、WebFetch、Read/Edit/Write）全开，不阉割
- 上下文窗口不限制，任务需要的历史都给够
- 允许多步推理与多轮迭代，**不设 max_iterations**——复杂任务本来就该多步
- 单次 `timeout ≥ 300s`（5 分钟），**不卡 30s**——思考需要时间

### 二、必须遵守的行为边界（防失控循环）

- 改动限定在任务明确指定的 `path:line`，**不顺手改其他文件**
- **不自动 commit / push / install 新依赖**（这三件事是循环重连的元凶）
- 不重构与本任务无关的代码
- 连续 **2 次失败立即停住并报告**，不要继续探索/重试
- Bash 删除类命令（`rm`/`del`/`Remove-Item`）→ 先报告再执行
- 网络请求 / 外部 API 调用 / 数据库写操作 → 先报告再执行
- 遇到锁文件 / 长时进程 / WebFetch 连续失败 → 不要硬扛，立即停住报告 sir

### 三、输出规范（省 token 版）

- 报告 ≤ 10 行：①改了什么（`path:line`） ②测试结果 ③遗留风险
- 函数 docstring ≤ 3 行，函数体内不写 `#` 注释（除关键 trade-off）
- **不复读本守则已固化的约束**——已固化就不重抄
- 改动行数预算：简单 ≤ 50 / 中等 ≤ 80 / 复杂 ≤ 150 行；超出 → 停下报告 sir
- 测试用例数量按指令执行，不多写"以防万一"

### 四、硬熔断（不靠 agent 参数，靠中转站预算）

- XMirai 中转站后台设**每日消费上限**（如 ¥80），超额自动熔断
- Codex 端**不设** RPM/TPM 速率限制——中转站速率通常不瓶颈，硬限反而让它排队重试更烧钱
- 单会话输入 >200K 或 >30 轮 → 收尾 commit，开新会话继续（沿用 §8）

### 五、本守则生效范围

- `D:\self\AGENTS.md` → 项目级，所有在 D:\self 下启动的 agent 默认遵守
- `C:\Users\57388\.codex\AGENTS.md` → 全局级，跨项目生效（待建）
- Codex 启动建议：`codex --approval-mode auto-edit --no-auto-commits --cd D:\self`
