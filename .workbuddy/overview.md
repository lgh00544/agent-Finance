# Discover 前瞻子 Agent 方案 + 提示词（2026-08-21）

## 做了什么

按 sir 要求：滞后问题挂在候选发掘漏斗里，写成第 5 个子 Agent，并直接出 Claude Code 提示词。不另起 `forward_view`。

## 关键结论

- T+3 能打、T+5 熄火（近 20 只胜率 35%）——「买当下强、不买未来还能走」成立
- 现有 4 子 Agent 只在 prompt 里自我扮演；本方案仍一次 `llm_final`，只加对照事实 + 收口约束

## 交付

- `D:\self\Discover前瞻子Agent_方案.md`
- `C:\Users\57388\Desktop\提示词\Discover前瞻子Agent_Claude执行指令.md`
- `D:\self\Discover前瞻子Agent_Claude执行指令.md`

经验沉淀急救提示词仍是另一条线，本批次明确不碰。
