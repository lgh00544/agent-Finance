"""AuditAgent 通用审核 Prompt（批1：只审 agent_suggestion）：正反辩论/反例/边界/裁决全在 LLM，代码只提供待审建议与历史 fail 原因。改 Prompt 文本后重启后端生效。"""

SYSTEM_PROMPT = """你是复盘建议的辩证审核官。对每一条策略优化建议做正反辩论式审核，输出中立、可落地的裁决。

硬性要求（必须全部满足）：
1. 强制正反辩论：先列出支持意见（至少 2 条），再强制找 1 条反对意见——不论你是否认同，必须找出来。
2. 反对意见必须含具体场景/反例（如「亨通惨案根因1」式真实反例或具体触发案例），禁止「可能存在风险」这类空话。
3. 至少给出 1 条边界场景：什么情况下这条建议会失效。
4. 至少 1 条基础库引用（K 编号 / 私有知识 ID / 反例库），格式如 K223、knowledge_id=42。
5. 找不到反对意见 → 强制 verdict=fail，并在 one_line_summary 写明「我没找到具体反方，但请 sir 复核」。
6. verdict 只能是 pass 或 fail：fail=建议存在实质缺陷需重思考；pass=可采纳。
7. dissent_view 至少 50 字且必须包含具体反例；support_view 至少 30 字；one_line_summary 不超过 40 字。"""


def build_user_prompt(suggestion: dict) -> str:
    """单条建议 → 首审 user 段（round1）"""
    return (
        f"【待审建议 #{suggestion.get('id')}】目标 Agent: {suggestion.get('target_agent')} 规则名: {suggestion.get('rule_name')}\n"
        f"当前值: {suggestion.get('current_value')} | 建议值: {suggestion.get('suggested_value')}\n"
        f"建议理由: {suggestion.get('reason')}\n"
        f"事实依据: {suggestion.get('evidence')}\n"
        f"预期效果: {suggestion.get('expected_effect')} | 风险提示: {suggestion.get('risk_note')}\n"
        "请按辩证审核官要求输出裁决。"
    )


def build_re_audit_user_prompt(suggestion: dict, dissent_view: str) -> str:
    """round=2 重审：追加历史 fail 原因，要求逐条回应"""
    return (
        f"【待审建议 #{suggestion.get('id')} · 重审 round2】\n"
        f"{build_user_prompt(suggestion)}\n"
        f"历史 fail 原因：{dissent_view}\n"
        "请明确逐条回应上述反对意见：若反对成立则 verdict=fail，若反对被证据化解则 verdict=pass。"
    )
