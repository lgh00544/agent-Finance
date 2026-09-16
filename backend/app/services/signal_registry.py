from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SignalResult(BaseModel):
    hit: bool
    value: float | str | None = None
    reason: str = "ok"


class SignalDef(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    id: str
    name: str
    layer: Literal["位置", "动量", "突破", "形态", "量价"]
    direction: Literal["buy", "sell"]
    params: dict = Field(default_factory=dict)
    func: Callable
    min_bars: int = 250
    status: Literal["candidate", "active", "deprecated"] = "candidate"
    version: str = "v1"


_REGISTRY: dict[str, SignalDef] = {}


def register(signal_id: str, name: str, layer: str, direction: str, params: dict | None = None):
    def decorator(func: Callable) -> Callable:
        _REGISTRY[signal_id] = SignalDef(id=signal_id, name=name, layer=layer, direction=direction,
                                         params=params or {}, func=func)
        return func
    return decorator


def list_all() -> list[SignalDef]:
    from app.signals import breakout, momentum, pattern, position, volume  # noqa: F401
    return sorted(_REGISTRY.values(), key=lambda item: item.id)


def list_active() -> list[SignalDef]:
    return [item for item in list_all() if item.status == "active"]


def get(signal_id: str) -> SignalDef | None:
    list_all()
    return _REGISTRY.get(signal_id)


def ready(features: dict, kline, min_bars: int = 250) -> SignalResult | None:
    """数据闸门：K 线不足 / 指标缺失 → 返回未触发结果，否则 None。"""
    if kline is None or len(kline) < min_bars:
        return SignalResult(hit=False, reason="insufficient_bars")
    return None if features else SignalResult(hit=False, reason="data_missing:indicators")


def evaluate(features: dict, kline, keys: str | tuple[str, ...], cond) -> SignalResult:
    """信号统一入口：数据闸门 → 关键字段缺失检查 → 判定；异常交由扫描层兜为 error:xxx。

    keys 为判定所需 features 字段（缺失记 data_missing:xxx），cond 取 features 返回 bool。"""
    gate = ready(features, kline)
    if gate is not None:
        return gate
    names = (keys,) if isinstance(keys, str) else tuple(keys)
    missing = next((name for name in names if features.get(name) is None), None)
    if missing is not None:
        return SignalResult(hit=False, reason=f"data_missing:{missing}")
    hit = bool(cond(features))
    return SignalResult(hit=hit, value=features.get(names[0]), reason="ok" if hit else "not_triggered")
