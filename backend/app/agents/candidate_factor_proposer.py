"""候选因子提议 Agent：只产出待人工审核的假设。"""
from pydantic import BaseModel, Field

from app.agents.common import ModelLevel, agent_call


class CandidateItem(BaseModel):
    candidate_id: str = ""
    name: str
    category: str = "主线"
    hypothesis: str
    formula: str = ""
    data_requirements: list[str] = Field(default_factory=list)
    expected_edge: str = ""
    risk_note: str = ""


class CandidateProposal(BaseModel):
    candidates: list[CandidateItem] = Field(min_length=3, max_length=5)


SYSTEM_PROMPT = """你是候选因子提议 Agent。基于已有因子失败案例，提出 3-5 个全新的可验证因子假设。
只输出结构化候选，不修改规则、不启用因子；每项要有名称、假设、公式、数据需求、预期优势和风险。"""


def propose_candidates(context: str = "", limit: int = 5) -> CandidateProposal:
    limit = max(3, min(int(limit), 5))
    return agent_call(
        agent="candidate_factor_proposer",
        cache_key=f"factor-candidates:{limit}:{context[:2000]}",
        system_prompt=SYSTEM_PROMPT,
        user_prompt=f"已有因子失败案例与约束：\n{context or '暂无，优先提出可由现有行情/财务数据验证的假设。'}\n数量上限：{limit}",
        schema=CandidateProposal, ttl_seconds=86400, model_level=ModelLevel.DEEP,
    )
