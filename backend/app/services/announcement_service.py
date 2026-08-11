"""
个股最新公告查询服务（对话链路增量能力）

【刚性代码逻辑】只做：股票代码解析、公告类型关键词定性、读库/抓取/入库编排、当日抓取去重标记。
全部研判（利好/利空/中性、交叉验证、风险提示）由对话层 LLM 结构化输出，本模块不做任何市场判断。

数据源复用（不重复造轮子）：
  - 抓取复用 akshare_source.fetch_news（东财搜索 → 空结果自动降级东财公告接口，
    公告行自带官方链接 data.eastmoney.com/notices/detail/…）
  - 存储复用 news_article 表 + repo.add_news（按 code+title 去重入库）
  - 节流复用项目 cache（fetch_news 自身 600s 缓存 + 本服务当日抓取标记）
"""
import logging
import re
from datetime import datetime, timedelta

from app.cache import cache
from app.db import repo
from app.datasource.fallback import get_datasource

logger = logging.getLogger(__name__)

# 公告类型关键词定性（客观规则，按优先级从高到低；纯文本匹配，不做主观判断）
_ANN_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("立案调查", ("立案", "立案调查", "被调查", "收到立案")),
    ("监管函", ("监管函", "问询函", "警示函", "关注函", "监管措施", "纪律处分", "行政处罚")),
    ("定增", ("定增", "非公开发行", "募集资金", "配股")),
    ("重组并购", ("重组", "并购", "收购", "重大资产", "吸收合并", "资产注入")),
    ("回购", ("回购", "股份注销")),
    ("业绩预告", ("业绩预告", "业绩预增", "业绩预减", "业绩快报", "预盈", "预亏", "预计净利润", "盈利预测")),
    ("重大合同", ("重大合同", "中标", "签署合同", "签订合同", "大额订单")),
    ("股权质押", ("质押", "解除质押")),
    ("高管增减持", ("增持", "减持", "持股变动", "举牌")),
    ("解禁", ("解禁", "限售股上市", "限售股份")),
    ("分红派息", ("分红", "派息", "利润分配", "除权除息", "送转")),
    ("停复牌", ("停牌", "复牌")),
]
_ANN_TYPE_DEFAULT = "其他"


def parse_stock_code(text: str) -> str | None:
    """从用户问题中解析 6 位 A 股代码（避免匹配到更长数字串中的片段）；未命中返回 None"""
    if not text:
        return None
    m = re.search(r"(?<!\d)(\d{6})(?!\d)", text)
    return m.group(1) if m else None


def classify_announcement(title: str) -> str:
    """公告类型关键词定性（客观规则；无法识别返回「其他」）"""
    t = title or ""
    for ann_type, keywords in _ANN_TYPE_RULES:
        if any(k in t for k in keywords):
            return ann_type
    return _ANN_TYPE_DEFAULT


def _days_left_today() -> int:
    """距今日 24:00 剩余秒数（当日标记缓存 TTL 用）"""
    now = datetime.now()
    return int((now.replace(hour=23, minute=59, second=59) - now).total_seconds()) + 1


def fetch_latest_announcement(stock_code: str, days: int = 7) -> dict:
    """查询某股近 N 日最新公告/新闻（对话链路工具能力）。

    流程：读库（news_article）→ 命中直接返回；库中无 → 当日未抓取过则调 fetch_news
    实时抓取并 add_news 去重入库 → 再读库返回。任何一步失败明确告知，绝不编造。
    返回：
      {stock_code, query_days, fetched, message, items: [{title, published_at, source,
        url, ann_type, summary}]}
    """
    code = str(stock_code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return {"stock_code": code, "query_days": days, "fetched": False,
                "message": f"股票代码无法解析（收到「{code}」），请提供 6 位 A 股代码后重试",
                "items": []}
    days = max(1, min(int(days or 7), 30))

    items = repo.get_recent_news(code, days)
    if not items:
        # 库中无近期数据 → 实时抓取（当日已抓取过则直接跳过外部请求，读库兜底）
        mark_key = f"announcement:fetched:{code}"
        if cache.get(mark_key) is None:
            try:
                source = get_datasource()
                news_df = source.fetch_news(code)
                stored = 0
                if news_df is not None and not news_df.empty:
                    for _, row in news_df.head(20).iterrows():
                        title = str(row.get("title") or "").strip()
                        if not title:
                            continue
                        try:
                            is_new = repo.add_news(
                                code, "", title, str(row.get("content") or ""),
                                str(row.get("source") or ""), str(row.get("url") or ""),
                                str(row.get("published_at") or ""))
                            stored += 1 if is_new else 0
                        except Exception as exc:  # noqa: BLE001 单条入库失败不中断抓取
                            logger.warning("公告入库失败 %s/%s: %s", code, title[:30], exc)
                    logger.info("公告抓取入库 %s: 获取%s条 新增%s条", code,
                                len(news_df), stored)
                cache.set(mark_key, "1", _days_left_today())
            except Exception as exc:  # noqa: BLE001 抓取失败明确告知，不编造
                logger.warning("公告抓取失败 %s: %s", code, exc)
                return {"stock_code": code, "query_days": days, "fetched": False,
                        "message": "外部公告接口抓取失败，请稍后重试（已读取库内既有记录）",
                        "items": []}
        items = repo.get_recent_news(code, days)

    rows = []
    for it in items:
        rows.append({
            "title": it["title"],
            "published_at": str(it["published_at"])[:19],
            "source": it["source"],
            "url": it["url"] or "链接未提供",
            "ann_type": classify_announcement(it["title"]),
            "summary": re.sub(r"\s+", " ", it["content"] or "")[:300],
        })
    if not rows:
        return {"stock_code": code, "query_days": days, "fetched": True,
                "message": "未查询到该标的近期公开公告（近%d日）" % days, "items": []}
    return {"stock_code": code, "query_days": days, "fetched": True,
            "message": "已查询到该标的近%d日公告/新闻%d条" % (days, len(rows)),
            "items": rows}
