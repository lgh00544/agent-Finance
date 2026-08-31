执行通用审核 Agent 批 1 最小闭环（只覆盖 agent_suggestion 1 个待审点）。

执行指令：直接读取并严格按 `D:\self\通用审核Agent_批1_最小闭环_Claude执行指令.md` 的 §一～§六 + 附 全部执行。
该文件 164 行已通过 sir 审核，§三规则 §四步骤 §五验证 §六红线 全部锁定，不要二次解读、不要扩展范围。

硬约束摘要（防你只读片段漏掉关键点）：
1. 本批只动 4 个新文件（init.sql 追加 audit_log / models.py 加 AuditLog+3字段 / audit_prompt.py / audit.py）+ 3 个改文件（schemas.py 追加 AuditOutput / repo.py 追加 5 函数 / routes.py _TASK_KINDS 注册 audit_pending）+ 1 个调度（jobs.py 加 audit_pending_job 挂 03:30 cron）。共 ≤ 8 个文件，改动 ≤ 250 行（不算 init.sql 和测试）。
2. 不动 review.py / agent_call / push_alert_node / task_queue.submit / llm_rethink_suggestion 既有逻辑。
3. 游标走 `repo.get_config('audit_cursor.last_id')` / `set_config(...)` 复用 `ExperienceConfig` 表，不引新表。
4. 失败重审调 `llm_rethink_suggestion(agent_suggestion.review_id, audit_log.dissent_view)`，最多 2 轮。
5. 老数据全部默认 pending/0/NULL，不补不迁移。
6. 测试只写 4 个（test_audit.py），不超。
7. 报告 ≤ 10 行：①文件清单 ②pytest 结果 ③遗留风险。

按 §0 路线"通用审核Agent_方案.md §3-§7"已过审，本批实现对齐方案，不重写架构。

执行完毕提交即可，无需再问。
