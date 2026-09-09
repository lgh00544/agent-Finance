"""行业消息雷达字典：人工种子 + 只读映射，不接受 LLM/反馈自动改字典。"""
from __future__ import annotations

import re

from app.db import repo


DEFAULT_SECTORS: list[dict] = [
    {"sector_code": "new_energy", "sector_name": "新能源", "aliases": ["锂电池", "光伏设备"],
     "entity_keywords": ["宁德时代", "比亚迪", "阳光电源", "隆基绿能"],
     "industry_keywords": ["锂", "电池", "电芯", "储能", "光伏"]},
    {"sector_code": "semiconductor", "sector_name": "半导体", "aliases": ["芯片"],
     "entity_keywords": ["中芯国际", "寒武纪", "长电科技", "北方华创"],
     "industry_keywords": ["半导体", "芯片", "晶圆", "光刻", "封测"]},
    {"sector_code": "medicine", "sector_name": "医药", "aliases": ["生物医药"],
     "entity_keywords": ["恒瑞医药", "药明康德", "百济神州"],
     "industry_keywords": ["创新药", "临床", "CRO", "医药", "疫苗"]},
    {"sector_code": "liquor", "sector_name": "白酒", "aliases": ["酿酒"],
     "entity_keywords": ["贵州茅台", "五粮液", "泸州老窖"],
     "industry_keywords": ["白酒", "高端酒", "动销", "批价", "酒企"]},
    {"sector_code": "bank", "sector_name": "银行", "aliases": ["银行业"],
     "entity_keywords": ["工商银行", "招商银行", "平安银行"],
     "industry_keywords": ["净息差", "信贷", "存款", "银行", "不良率"]},
    {"sector_code": "real_estate", "sector_name": "房地产", "aliases": ["地产"],
     "entity_keywords": ["万科A", "保利发展", "招商蛇口"],
     "industry_keywords": ["地产", "商品房", "房贷", "土拍", "去库存"]},
    {"sector_code": "defense", "sector_name": "国防军工", "aliases": ["军工"],
     "entity_keywords": ["中航沈飞", "航发动力", "中国船舶"],
     "industry_keywords": ["军工", "航空装备", "船舶", "军贸", "卫星"]},
    {"sector_code": "ai_compute", "sector_name": "AI算力", "aliases": ["人工智能", "算力"],
     "entity_keywords": ["中际旭创", "新易盛", "浪潮信息"],
     "industry_keywords": ["AI", "算力", "服务器", "光模块", "数据中心"]},
]

SEED_STOCK_CODES: dict[str, list[str]] = {
    "new_energy": ["300750", "002594", "300274", "601012"],
    "semiconductor": ["688981", "688256", "600584", "002371"],
    "medicine": ["600276", "603259", "688235"],
    "liquor": ["600519", "000858", "000568"],
    "bank": ["601398", "600036", "000001"],
    "real_estate": ["000002", "600048", "001979"],
    "defense": ["600760", "600893", "600150"],
    "ai_compute": ["300308", "300502", "000977"],
}


def ensure_default_dict() -> int:
    return repo.upsert_sector_dict([{**r, "version": "v1", "source": "manual"} for r in DEFAULT_SECTORS])


def list_active_sectors() -> list[dict]:
    ensure_default_dict()
    return repo.list_sector_dict()


def seed_stock_codes(sector: dict) -> list[str]:
    """人工种子标的兜底：只用于抓 company_signal，不代表完整行业成分。"""
    code = str(sector.get("sector_code") or "")
    return list(SEED_STOCK_CODES.get(code, []))


def map_text(text: str, source_sector: dict | None = None) -> dict:
    """返回多行业映射；source_sector 来自成分股枚举时只标 source_tag 代理归属。"""
    sectors = list_active_sectors()
    norm = re.sub(r"\s+", "", text or "").lower()
    matches: list[dict] = []
    for s in sectors:
        exact_entity = [k for k in (s.get("entity_keywords") or []) if k and k.lower() in norm]
        exact_keyword = [k for k in (s.get("industry_keywords") or []) if k and k.lower() in norm]
        aliases = [k for k in (s.get("aliases") or []) if k and k.lower() in norm]
        if exact_entity or exact_keyword or aliases:
            method = "exact_entity" if exact_entity else "exact_keyword"
            hit_count = len(exact_entity) + len(exact_keyword) + len(aliases)
            matches.append({**s, "mapping_method": method,
                            "mapping_confidence": min(1.0, 0.35 + hit_count * 0.15)})
    if not matches and source_sector:
        matches.append({**source_sector, "mapping_method": "source_tag",
                        "mapping_confidence": 0.6})
    if not matches:
        return {"sector_codes": [], "mapping_method": "unmapped",
                "mapping_confidence": 0.0, "matches": []}
    method_order = {"exact_entity": 3, "exact_keyword": 2, "source_tag": 1}
    method = max((m["mapping_method"] for m in matches), key=lambda x: method_order.get(x, 0))
    confidence = max(float(m["mapping_confidence"]) for m in matches)
    return {"sector_codes": [m["sector_code"] for m in matches],
            "mapping_method": method, "mapping_confidence": confidence, "matches": matches}
