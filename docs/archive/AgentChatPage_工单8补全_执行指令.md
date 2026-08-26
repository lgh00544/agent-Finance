# 工单8 AgentChatPage 补全

## 目标
补齐 AgentChatPage 相对旧版 10_Agent对话.py 缺失的 5 块。**仅改 web/src/pages/AgentChatPage.tsx 单文件**，后端/API/类型零改动（接口全实存：chatAsk/chatRule/chatLearn(已支持 description)/chatLearnConfirm/chatHistory 带 message_type）。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| Agent 选择区 | 选中后下方加「职责范围」+「知识库来源」两块（ChatAgentMeta.scope / knowledge） | 替代当前仅 scope 小字 |
| ask 回答卡 | 补 scope_note info 行；result.announcement 存在时渲染公告卡（sentiment 利好绿/利空红/中性灰 + verdict.reason/cross_check/risk_note + items 前 8 条：日期/标题/来源/类型，url 有效则套 <a>）| 对齐旧版 _render_announcement |
| rule tab | **独立 ruleTid state**（替换现在共用 askTid），结果在 rule tab 内渲染：verdict 结论（adopted=已采纳绿 / partial=部分采纳橙 / 其他=维持原规则灰）+ reason 依据 + conflict_note 冲突核查 + rule_title + knowledge_id | 修复"规则调教结果显示在文字提问 tab"的错位 bug |
| learn tab | 上传区加「补充说明」textarea（≤500 字，传入 chatLearn 第 4 参 description，当前硬编码传 ''）；结果渲染改结构化（engine / 用户说明 / summary + points 列表逐条可编辑：标题 Input + 正文 TextArea + 标签 Input + 目标 Agent Select(all+agents)）；确认沉淀传 {title,content,tags[],agent_tag} | profile 现有 learn 仅 textarea+按 title/content 过滤 |
| 对话历史 | 卡片加状态流转 Tag（待确认→已完成→归档，点击切换，localStorage 按 agent 前缀隔离） | 替代纯列表；纯前端态不落库 |

## 红线

1. 只改 `web/src/pages/AgentChatPage.tsx`；禁止动 backend / api/chat.ts / types
2. 不新增依赖（仅 antd 已有组件：Card/Select/Input/TextArea/Tag/Button/Form/Space/Segmented 或 Dropdown）
3. 复用现有 task 轮询模式（refetchInterval 2000ms）；不触发额外请求
4. 空数据一律不渲染或「—」；不编造
5. learn 确认沉淀沿用现有 chatLearnConfirm(agent, entries) 调用方式

## 验收清单

- [ ] 5 处补全齐全（职责/知识库卡片、ask 公告卡+scope_note、rule 结果本 tab 渲染、learn 说明+结构化编辑、历史状态流转）
- [ ] rule 提交后结果显示在「规则调教」tab（不再错位到文字提问）
- [ ] tsc -b + npm build 0 error；oxlint 0 error
- [ ] 多模态上传带补充说明后，结果区显示用户说明
- [ ] 展示图片上传点数：未输说明也能正常上传（description 缺省 ''）

## 参考
- 旧版：D:\self\streamlit\pages\10_Agent对话.py（_render_announcement / 左右布局职责知识卡 / learn 修正 / 历史看板）
- 类型：web/src/types/index.ts:398-417（ChatAgentMeta.scope/knowledge / ChatMessage.scope_note）
- API：web/src/api/chat.ts:53-66（chatLearn 第 4 参 description）