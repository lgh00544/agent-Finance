"""LLM 调用统计（当日累计，供首页「系统运行状态」看板）
【刚性代码逻辑】只做计数聚合，不产生任何研判内容。

指标来源：DeepSeek 每次响应的 usage 字段——prompt_cache_hit_tokens /
prompt_cache_miss_tokens / completion_tokens；调用层在每次成功响应后写入。
存储：缓存抽象层（dev=内存 / prod=Redis），按自然日分区，跨进程为近似值
（进程内锁保护，不做分布式原子计数，统计误差可忽略）。
"""
import json
import threading
import time

from app.cache import cache
from app.core.config import settings

_lock = threading.Lock()
_KEY_TTL = 172800  # 2 天，跨午夜保留当日与昨日


def _empty() -> dict:
    # 工厂函数而非模块级常量：避免浅拷贝共享 "models" 子字典，
    # 否则 record() 的 setdefault 会把条目永久写进共享对象
    return {"requests": 0, "hit_tokens": 0, "miss_tokens": 0,
            "completion_tokens": 0, "cost_yuan": 0.0, "models": {}}


def _key() -> str:
    return f"llm_stats:{time.strftime('%Y-%m-%d')}"


def _load() -> dict:
    raw = cache.get(_key())
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _price_for(model: str) -> tuple[float, float, float]:
    """按模型名选单价（元/百万 tokens）：模型名含 'minimax' 用 MiniMax 单价，否则 DeepSeek 单价。
    未填写（全 0）时 cost 恒 0 = 不计成本（向后兼容）。"""
    if "minimax" in (model or "").lower():
        return (settings.minimax_input_price, settings.minimax_input_price,
                settings.minimax_output_price)
    return (settings.deepseek_cached_input_price, settings.deepseek_input_price,
            settings.deepseek_output_price)


def _calc_cost(model: str, hit_tokens, miss_tokens, completion_tokens,
               cost: float | None) -> float:
    """成本（元，四舍五入到分）。显式 cost 优先；否则按单价表自动计算。
    token 可能为 None（structured.py 透传 usage 字段），一律按 0 处理。
    单价为 0 时结果恒 0，不改变既有行为。"""
    if cost is not None:
        return round(float(cost), 2)
    cached_p, input_p, output_p = _price_for(model)
    total = (int(hit_tokens or 0) * cached_p + int(miss_tokens or 0) * input_p
             + int(completion_tokens or 0) * output_p) / 1_000_000.0
    return round(total, 2)


def record(model: str, hit_tokens: int, miss_tokens: int,
           completion_tokens: int, cost: float | None = None) -> None:
    """记录一次成功响应：模型名 + 命中/未命中/输出 token 数（均以服务端 usage 为准）。
    cost 可选：缺省时按模型名单价表自动计算（向后兼容，旧调用不传 cost 行为不变，仅新增成本统计）。"""
    with _lock:
        stats = {**_empty(), **_load()}
        stats["requests"] += 1
        stats["hit_tokens"] += max(0, int(hit_tokens or 0))
        stats["miss_tokens"] += max(0, int(miss_tokens or 0))
        stats["completion_tokens"] += max(0, int(completion_tokens or 0))
        stats["cost_yuan"] = round(stats["cost_yuan"]
                                   + _calc_cost(model, hit_tokens, miss_tokens,
                                                completion_tokens, cost), 2)
        m = stats["models"].setdefault(model, {"calls": 0})
        m["calls"] += 1
        cache.set(_key(), json.dumps(stats, ensure_ascii=False), _KEY_TTL)


def snapshot() -> dict:
    """当日快照（供前端展示）：请求次数 / 命中·未命中 token / 缓存命中率 / 模型分布 / 截止时间"""
    stats = {**_empty(), **_load()}
    total_in = stats["hit_tokens"] + stats["miss_tokens"]
    hit_rate = round(stats["hit_tokens"] / total_in * 100, 1) if total_in else None
    models = [
        {"model": name, "calls": m["calls"],
         "pct": round(m["calls"] / stats["requests"] * 100, 1) if stats["requests"] else 0.0}
        for name, m in sorted(stats["models"].items(), key=lambda kv: -kv[1]["calls"])
    ]
    return {
        "date": time.strftime("%Y-%m-%d"),
        "requests": stats["requests"],
        "hit_tokens": stats["hit_tokens"],
        "miss_tokens": stats["miss_tokens"],
        "completion_tokens": stats["completion_tokens"],
        "hit_rate_pct": hit_rate,
        "cost_yuan": stats["cost_yuan"],
        "models": models,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
