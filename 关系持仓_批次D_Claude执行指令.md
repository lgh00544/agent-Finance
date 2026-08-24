# 关系持仓批次 D · 派发期自动判定 · Claude Code 执行指令

> 生成：Lark · 执行：Claude Code（D:\self）· 决策：sir · 方案：`关系持仓_个股分析_优化方案.md` §三模块1 · 起点：§四步骤1

## 一、目标 + 约束

**做**：新建 `distribution_phase.py` + `DistributionPhaseLog` 表；注入 Monitor/Sell/Score 三 Agent `collect` 段；新增 `GET /api/distribution_phase/{code}` + 每日 15:30 `distribution_phase_job`。

**不做**：不动 `agent_call`/`push_alert_node`；不改 5 维权重（派发期只作"风险维度"参考，不单独占一维）；不动 Streamlit；不引新库（仿 `sector_snapshot` 风格）。

**5 铁律**：①Agent 解耦（只读不调用）②代码算 6 维+phase（0-5），LLM 做综合判断 ③缺数据 → null + `missing_data` 明列，不补零 ④confidence=高/中/低是参考非死条件 ⑤confidence=低时 `phase_label="拉升期?"`（前端徽章变灰）

## 二、规则

**6 维口径**（参考 K175）：时间=`5日累计/20日累计`；空间=距52周高+距52周低；量价=`(近5日均量/20日均量 - 1) - (近5日涨幅/20日涨幅)`；主力=连续净流入日数-净流出日数；形态=近10日反转形态计数（双顶/头肩顶/跌破颈线）；政策=近30日事件数占位（无数据→null）。

**phase 映射**（≥N 维触发即升级）：0=拉升期(0) / 1=初期派发(1-2) / 2=砸盘期(3) / 3=反弹期(4) / 4=末跌期(5) / 5=触底期(6维触发+20日跌幅>30%)。

**confidence**：高=6维齐 / 中=缺1-2维 / 低=缺≥3维或异常。

**注入字段**（3 Agent 各 1 个，统一名 `distribution_phase_context`）：Monitor 在批次 F 注入的 3 字段**后**追加；Sell 在 `portfolio_risk_context` **后**追加；Score 作为减分项（phase≥2 时评分上限 -10，不单独占一维）。

**返回 Schema**：
```
{"phase":0,"phase_label":"拉升期?","confidence":"低",
 "six_dim":{"time":{"value":0.8,"triggered":true}, ... , "policy":null},
 "missing_data":["volume_price","policy"]}
```

## 三、执行顺序

**1 读已有代码**（必做不写）：`services/holding_view.py`（纯计算风格）+ `services/sector_snapshot.py`（SimpleCache+24hTTL）+ `db/models.py:652` SectorSnapshot + `db/init.sql` sector_snapshot DDL + `agents/monitor.py:173` collect 段（批次F已注入3字段的位置）+ `agents/sell.py` collect + `agents/score.py` collect + `api/routes.py` profile 端点 L785/791/800/809（仿风格）+ `scheduler/jobs.py:228` sector_refresh_job + `:395/:423` job_status。

**2 新建 `services/distribution_phase.py`**：6 维函数（每个返回 `{"value":float|None,"triggered":bool}` 或 None）+ 主入口 `compute_distribution_phase(symbol, trade_date) -> dict` + `SimpleCache().get_or_set(key=f"distribution_phase:{trade_date}:{symbol}", ttl=86400)`。

**3 新建 `DistributionPhaseLog` 表**：`models.py` 仿 `:652` 加 `id/trade_date/symbol/phase/phase_label/confidence/six_dim(JSON)/missing_data(JSON)/created_at/updated_at`；`init.sql` 仿 sector_snapshot DDL；`db/session.py` 加 `_ensure_distribution_phase_table()`。

**4 注入 3 Agent**：`monitor.py:173 后` / `sell.py portfolio_risk_context 后` / `score.py 风险维度参考`（phase≥2 评分上限-10）。

**5 路由 + cron**：`routes.py` 加 `GET /api/distribution_phase/{stock_code}`（`?force=true` 跳缓存）；`jobs.py` 加 `distribution_phase_job` 每日 15:30 遍历"今日候选+当前持仓"，落 DistributionPhaseLog；`job_status()` 加 `last_distribution_phase_run`（仿 `:423`）。

**6 测试 + 收尾**：新建 `tests/test_distribution_phase.py` ≤ 5 用例——①6维时间计算正确 ②缺数据不补零+missing_data ③缺3维→confidence低+phase_label加`?` ④路由返回完整 6 维 ⑤3 collect 段正确注入字段。

```
pytest tests/test_distribution_phase.py -v
pytest tests/ -v
mypy backend/app/services/distribution_phase.py
```

提交（不 push）：
```
git add -A
git commit -m "[批次D] 派发期自动判定落地：6维计算 + DistributionPhaseLog 表 + 3 Agent 注入 + 路由 + cron"
```

## 四、红线

1. 不动 agent_call / push_alert_node
2. 不碰交易规则表（6 维阈值是参考非死条件）
3. 不编造数值（缺→null+missing_data）
4. 不动 Streamlit
5. 不引新库（仿 sector_snapshot 走 SQLite）

**Claude Code 端省 token 6 条**：①禁止复读方案全文，只 grep "模块1"/"派发期"/"K175" ②只动本批次 6 类文件，禁止顺手改其他 ③docstring ≤ 3 行，函数体内不写 # 注释 ④复用已有函数（`fetch_industry_spot`/`compute_drawdown_decomposition`/`_ensure_sector_snapshot_table` 等），禁止重写 ⑤测试 ≤ 5 个 ⑥报告 ≤ 10 行（改了什么+测试结果+遗留风险）。

**代码侧最小改动**：≤150 行（不含 service 函数体）+ service 函数体 ≤ 80 行 + init.sql 追加 ≤ 15 行；超出→停下报告 sir。

## 五、沟通节点

每步骤完成后输出 ①改了哪些文件 ②测试结果 ③遗留风险；遇字段含义不清/阈值歧义→停下问 sir；遇红线触碰→立即停下报告；批次 D 完成后停等验收，再进批次 E。
