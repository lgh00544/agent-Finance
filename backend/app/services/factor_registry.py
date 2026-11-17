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
    # S-9/F-9：因子方向 —— 原始值越低越好的负向因子（估值类 f09/f10/f12、负债率 f21、
    # 拥挤度 f25）direction=-1，IC 计算时对原始值取反，保证「IC>0 即预示未来收益更高」
    # 的方向一致；其余因子默认 1（原始值越高越好）。rank IC 单调反转等价于对值取反。
    direction: Literal[1, -1] = 1


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
        direction=-1 if fid in {"f09", "f10", "f12", "f21", "f25"} else 1,
    )
    return func


def list_all() -> list[FactorDef]:
    """全量注册因子（含 deprecated 与 custom），按 id 排序，供注册表快照展示。"""
    return sorted(_REGISTRY.values(), key=lambda d: d.id)


def list_active() -> list[FactorDef]:
    return [f for f in _REGISTRY.values() if f.status == "active"]


def get(fid: str) -> FactorDef | None:
    return _REGISTRY.get(fid)


# ---- P-11（A-14/F-6/F-7）：因子状态/权重人工拍板写回 + 缓存指纹 ----
def set_factor_status(fid: str, status: str) -> FactorDef:
    """人工拍板：改写因子启停状态（active/deprecated）。状态变更后 fingerprint 变化 → 评分缓存自动失效。"""
    if status not in ("active", "deprecated"):
        raise ValueError(f"status 必须为 active/deprecated，收到: {status!r}")
    row = _REGISTRY.get(fid)
    if row is None:
        raise KeyError(f"因子不存在: {fid}")
    row.status = status
    return row


def set_factor_weight(fid: str, weight_hint: float) -> FactorDef:
    """人工拍板：改写因子权重提示（0~1）。写回后进缓存指纹。"""
    weight_hint = float(weight_hint)
    if not 0 <= weight_hint <= 1:
        raise ValueError(f"weight_hint 必须在 0~1，收到: {weight_hint}")
    row = _REGISTRY.get(fid)
    if row is None:
        raise KeyError(f"因子不存在: {fid}")
    row.weight_hint = weight_hint
    return row


def register_custom(def_: FactorDef) -> None:
    """候选因子真实启用：把可执行公式解析后的候选因子注册进运行期 registry。"""
    if def_.id in _REGISTRY and _REGISTRY[def_.id].version != "custom":
        raise ValueError(f"因子 id 冲突: {def_.id} 已被内置因子占用")
    _REGISTRY[def_.id] = def_


def unregister(fid: str) -> None:
    """候选因子停用：从运行期 registry 移除（仅允许移除 custom 版本）。"""
    row = _REGISTRY.get(fid)
    if row is not None and row.version == "custom":
        _REGISTRY.pop(fid, None)


def fingerprint() -> str:
    """全注册因子状态指纹：拍板写回状态/权重/方向/版本任一项变化即变化，用于评分缓存键。"""
    parts = []
    for fid in sorted(_REGISTRY):
        row = _REGISTRY[fid]
        parts.append(f"{fid}:{row.status}:{row.weight_hint:.4f}:{row.direction}:{row.version}")
    return "|".join(parts) or "empty"


# ---- 启停持久化：状态落 factor_status 表，重启由 sync_from_db 恢复 ----
def _upsert_status(fid: str, status: str, reason: str, decided_by: str) -> None:
    from app.db.models import FactorStatus
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        row = db.get(FactorStatus, fid)
        if row is None:
            row = FactorStatus(factor_id=fid)
            db.add(row)
        row.status = status
        row.reason = (reason or "")[:255] or None
        row.decided_by = decided_by
        db.commit()


def record_proposal(fid: str, reason: str) -> None:
    """回测判出的失效候选只落提案（proposed），不生效；须人工确认后才下线。"""
    if fid not in _REGISTRY:
        return
    _upsert_status(fid, "proposed", reason, "auto")


def decide(fid: str, status: str, reason: str = "") -> FactorDef:
    """人工拍板：落库 + 立即改内存。status=deprecated 即下线，active 即驳回恢复。"""
    if status not in ("active", "deprecated"):
        raise ValueError(f"status 必须为 active/deprecated，收到: {status!r}")
    if fid not in _REGISTRY:
        raise KeyError(f"因子不存在: {fid}")
    _upsert_status(fid, status, reason, "manual")
    return set_factor_status(fid, status)


def list_status_rows() -> list[dict]:
    """因子启停留痕全量（含 proposed 待确认项），供前端候审与审计。"""
    from app.db.models import FactorStatus
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        rows = db.query(FactorStatus).order_by(FactorStatus.updated_at.desc()).all()
        return [{"factor_id": r.factor_id, "status": r.status, "reason": r.reason,
                 "decided_by": r.decided_by,
                 "updated_at": r.updated_at.isoformat() if r.updated_at else None}
                for r in rows]


def sync_from_db() -> int:
    """启动时把已拍板状态载入内存注册表；proposed 不生效（避免未经确认就下线因子）。"""
    applied = 0
    for item in list_status_rows():
        row = _REGISTRY.get(item["factor_id"])
        if row is None or item["status"] not in ("active", "deprecated"):
            continue
        row.status = item["status"]
        applied += 1
    return applied
