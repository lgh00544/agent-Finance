from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FactorResult(BaseModel):
    value: float | int | str | None
    quantile: float | None = None
    reason: str = ""


class FactorDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str
    name: str
    category: Literal["动量", "催化", "估值", "资金", "质量", "主线"]
    func: Callable
    has_quantile: bool
    weight_hint: float = Field(ge=0, le=1)
    status: Literal["active", "deprecated"] = "active"
    version: str = "v1"


_CATEGORIES = ("动量",) * 5 + ("催化",) * 3 + ("估值",) * 4 + ("资金",) * 5 + ("质量",) * 4 + ("主线",) * 4
_NAMES = "MA20偏离度 MACD状态 20日收益 量比 威科夫相位 业绩催化 政策催化 行业事件 PE PB PEG PS 主力净流入占比 北向资金 游资席位 龙虎榜次数 融资融券余额 ROE 毛利率 经营现金流/营收 资产负债率 板块强度 板块资金 轮动位置 板块拥挤度".split()
_QUANTILES = {"f01", "f03", "f04", "f09", "f10", "f11", "f12", "f13", "f18", "f19", "f20", "f21", "f22", "f23"}
_REGISTRY: dict[str, FactorDef] = {}


def register(func: Callable) -> Callable:
    fid = func.__name__.split("_", 1)[0]
    idx = int(fid[1:]) - 1
    weight = 0.20 if idx < 8 else 0.15
    _REGISTRY[fid] = FactorDef(
        id=fid, name=_NAMES[idx], category=_CATEGORIES[idx], func=func,
        has_quantile=fid in _QUANTILES, weight_hint=weight,
    )
    return func


def list_active() -> list[FactorDef]:
    return [f for f in _REGISTRY.values() if f.status == "active"]


def get(fid: str) -> FactorDef | None:
    return _REGISTRY.get(fid)
