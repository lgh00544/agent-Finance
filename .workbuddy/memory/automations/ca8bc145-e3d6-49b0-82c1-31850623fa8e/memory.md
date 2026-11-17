# 因子 IC 月度回测提醒 — 执行历史

## 2026-11-13（首次运行）

- 提醒内容本身与库内实况不符，已当面纠正：cron 于 11-01 02:00 触发并记 ok，但 `factor_ic_history` 最新期仍为 2026-07，缺 08/09/10/11 四个月；`job_run_log` 的 ok 是假的（服务层软失败正常 return，包装层看不到）。
- 25 个注册因子中 15 个样本恒 0（估值 4/4、资金 5/5 全灭），实际只有 10 个在算。
- 无任何因子满足「连续 3 月 |IC|<0.02」，本期无需 disable。
- 25 条 factor_candidate 全 pending，`validation_result` 的 mean_ic/ir 全为 null（只有 periods/rows 占位）→ 不可 enable。
- 权重 4 套为 6 维度（非 25 因子级）；当日 total_score=11 → 防御期 → 防御市已自动生效，无需手动切。
- 已修两处代码（未 commit）：`factor_ic.judge_status` 改按 |IC| 判定；`jobs.py` 增加 `job:status_override_*` 使零产出落 error。测试 30 passed。
- 未执行：4 个月补跑（联网 30–75 分钟）、15 个零样本因子归因。均待 sir 一句话。

## 下次运行要点

1. 先查 `factor_ic_history` 最新 period 是否 ≥ 上月，别信 `job_run_log.last_status`。
2. 若仍停留在 2026-07，说明补跑没做，直接报「数据未恢复」，不要按月份提醒 sir 看红黄绿。
3. 候选因子 enable 前必须看到 mean_ic / ir 有实际数值，全 null 一律不动。
4. IC 只有 API 一个消费方，不影响打分/权重——回复 sir 时不要说成「影响选股」。
5. 失效候选现走 `GET /api/factor-status`（status=proposed），需人工确认才下线；报「待确认 N 个」而不是「已下线 N 个」。
