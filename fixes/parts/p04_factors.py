# -*- coding: utf-8 -*-
'''factors 修复：P0-6④ 财报前视（披露滞后）/ P0-6③ 复权口径 / M20 跨源量纲 / P0-7 脏样本

涉及：
  backend/app/factors/data_adapter.py   —— latest() 披露滞后约束、as_of 路由、跨源来源白名单
  backend/app/services/factor_ic.py     —— 快照日传入 adapter、复权口径校验、IC 样本净化

嵌入的代码片段一律用三单引号包裹（原文含三双引号 docstring）。
每个 old 均以实际 read 内容逐字抄录，且在当前文件中恰好出现一次。

取舍与未修复项见交付报告；kline_store.py / valuation.py / quality.py 未改动（原因见报告）。
'''

NAME = "factors"

_ADAPTER = "backend/app/factors/data_adapter.py"
_IC = "backend/app/services/factor_ic.py"

ITEMS = [
    # ------------------------------------------------------------------ P0-6④
    {
        "id": "P0-6-4",
        "file": _ADAPTER,
        "summary": "latest() 增加披露日滞后约束（as_of），财报/资金流按快照日取用，消灭回测前视",
        "edits": [
            # (1) 日期工具：披露滞后需要自然日平移
            #     注：`import unicodedata` 是 M19（p05_api_auth.py 片段）的 `_norm_sector()` 所需，
            #     由本 edit 一并加入 —— import 区只由本片段改，避免两个片段改同一行导致应用顺序敏感。
            ('''import math
from typing import Any

import pandas as pd''',
             '''import math
import unicodedata
from datetime import datetime, timedelta
from typing import Any

import pandas as pd'''),
            # (2) latest() 本体 + 滞后缓冲常数
            ('''def latest(items: list[dict], date_keys: tuple[str, ...] = ("report_date", "date")) -> dict:
    """取最新一期：以行内日期字段的最大值为准，不依赖列表位置。

    各数据源返回顺序并不统一（实查 financial / fund 均为「最新在前」降序），
    沿用 items[-1] 会取到最旧一期：f11/f18-f21 曾因此在读 2001 年财报、roe 恒为 None。
    rows 无可用日期字段时（如 sector_rows 的板块快照，源本身只有板块名/涨跌幅等、
    没有日期列）保留原行为 items[-1]，不静默改取 [0]。
    """
    if not items:
        return {}
    dated = [(str(row.get(key)).strip(), row) for row in items for key in date_keys
             if str(row.get(key) or "").strip()]
    return max(dated, key=lambda pair: pair[0])[1] if dated else items[-1]''',
             '''# P0-6④：披露滞后缓冲（自然日）—— 只接受「报告期 + 缓冲 ≤ as_of」的期次。
# 报告期（report_date）是「数据所属期间」，披露日才是「市场可见时点」：2026-03-31 的一季报
# 到 4 月底才披露，若 3-31 的快照就用它，回测/打分等于用了当时市场还没看到的数据（前视）。
# 缓冲按 A 股法定披露截止日**分类**给（各报告期 → 截止日间隔的自然日数）：
#   年报 12-31 → 次年 4-30（120 天）、一季报 03-31 → 4-30（30 天）、
#   中报 06-30 → 8-31（62 天）、三季报 09-30 → 10-31（31 天）。
# 为什么不能一律取 120 天：统一 120 天会把「4 月底就已披露的一季报」误判成 7 月底才可见，
# 于是 5/6/7 三个月的快照会退回上年年报 —— 那不是保守，而是**口径错误**（当时的真实可得
# 数据被当成不可得），f11/f18-f21 的 IC 会被建立在一个并不存在的时间线上；反过来统一取
# 30 天又会让年报在 4 月前就可用（真前视）。故必须按报告期分类。
# 未识别的报告期一律退回最保守的 DISCLOSURE_LAG_DAYS；调用方可用 disclosure_lag_days=<int>
# 强制统一值（显式覆盖优先）。
DISCLOSURE_LAG_DAYS = 120                  # 兜底（未知报告期）/ 显式统一覆盖时的兼容默认值
_DISCLOSURE_LAG_BY_REPORT: dict[str, int] = {
    "12-31": 120, "03-31": 30, "06-30": 62, "09-30": 31,
}
# 资金流是行情数据（T+1 已可得），不是定期报告：单独给 1 天缓冲，不套用法定披露缓冲。
FUND_FLOW_LAG_DAYS = 1


def latest(items: list[dict], date_keys: tuple[str, ...] = ("report_date", "date"),
           as_of: str | None = None, disclosure_lag_days: int | None = None) -> dict:
    """取最新一期：以行内日期字段的最大值为准，不依赖列表位置。

    各数据源返回顺序并不统一（实查 financial / fund 均为「最新在前」降序），
    沿用 items[-1] 会取到最旧一期：f11/f18-f21 曾因此在读 2001 年财报、roe 恒为 None。
    rows 无可用日期字段时（如 sector_rows 的板块快照，源本身只有板块名/涨跌幅等、
    没有日期列）保留原行为 items[-1]，不静默改取 [0]。

    P0-6④（披露滞后约束）：给定 as_of（快照日）时只接受「报告期 + 披露缓冲 ≤ as_of」的期次，
    即只用当时市场已看到的那一期。缓冲默认按报告期查 _DISCLOSURE_LAG_BY_REPORT
    （年报 120 / 一季报 30 / 中报 62 / 三季报 31 天），传 disclosure_lag_days=<int> 则强制统一值。
    as_of 缺省（None）不做任何过滤 —— 线上实时打分路径与既有调用方/测试行为逐字不变
    （向后兼容优先）。
    有资格的行被滞后约束全部排除时返回 {}（空字典），绝不退回 items[-1]：宁可让调用方
    判空（因子记 data_missing），也不取未经披露校验的一期造成前视。
    日期按 YYYY-MM-DD 字符串比较（与取值口径一致）；as_of 非该格式时不新增过滤，不编造口径。
    """
    if not items:
        return {}
    dated = [(str(row.get(key)).strip(), row) for row in items for key in date_keys
             if str(row.get(key) or "").strip()]
    if not dated:
        return items[-1]          # 无日期字段（板块快照等）：保留原行为
    if as_of:
        try:
            base = datetime.strptime(str(as_of)[:10], "%Y-%m-%d")
        except (TypeError, ValueError):
            base = None           # as_of 不是 YYYY-MM-DD：保持原行为，由调用方保证格式
        if base is not None:
            def _disclosed(period: str) -> bool:
                """该报告期到 as_of 时是否已过法定披露截止日（按报告期分类缓冲）。"""
                lag = disclosure_lag_days
                if lag is None:
                    # period 形如 "YYYY-MM-DD..."，取 "MM-DD" 判报告类型
                    lag = _DISCLOSURE_LAG_BY_REPORT.get(period[5:10], DISCLOSURE_LAG_DAYS)
                limit = (base - timedelta(days=int(lag))).strftime("%Y-%m-%d")
                return period[:10] <= limit

            dated = [pair for pair in dated if _disclosed(pair[0])]
            if not dated:
                return {}
    return max(dated, key=lambda pair: pair[0])[1]'''),
            # (3) 带 as_of 的取数入口（不改 find/quote 等其他方法）
            ('''    def hot_money(self) -> dict:
        value = self._cache.get("hot_money") or self.extra.get("hot_money")
        return value if isinstance(value, dict) else {}''',
             '''    def hot_money(self) -> dict:
        value = self._cache.get("hot_money") or self.extra.get("hot_money")
        return value if isinstance(value, dict) else {}

    def latest_financial(self) -> dict:
        """最新一期财报（P0-6④）：extra 带 as_of 快照日时叠加披露滞后约束，避免前视。

        无 as_of 时（线上实时路径，extra 只有 trade_date）与 latest() 原行为完全一致。
        """
        return latest(self.financial_rows(), as_of=self.extra.get("as_of"))

    def latest_fund(self) -> dict:
        """最新一期资金流（P0-6④）：资金流是行情数据（T+1 已可得），滞后按日计，
        不套用定期报告的 120 天法定披露缓冲；同样只在给定 as_of 时启用过滤。
        """
        return latest(self.fund_rows(), as_of=self.extra.get("as_of"),
                      disclosure_lag_days=FUND_FLOW_LAG_DAYS)'''),
        ],
    },
    # ------------------------------------------------------------------ M20
    {
        "id": "M20",
        "file": _ADAPTER,
        "summary": "find() 按 key 白名单限定来源 + find_in()/量纲注释，阻断跨源量纲混用",
        "edits": [
            # (1) 来源白名单常量（只列有歧义的 key，其余行为不变）
            ('''def factor(value: Any, reason: str = "ok", quantile: float | None = None) -> FactorResult:''',
             '''# M20：跨源同名 key 的来源白名单 —— 各数据源的同名字段量纲/口径并不通用
# （资金流净额「元」、板块快照「涨跌幅%」、实时行情是 tick 级快照），而 find() 原本
# 「谁先有谁命中」，于是 find("main_net_inflow") 落 fund、find("amount") 被 quote 抢答，
# 两者相除就静默错数量级（且 quote 与历史 fund 行不同期）。
# 只列「已知会产生数量级/同期性歧义」的 key；未列出的 key 行为完全不变（不引入大重构）。
# 需要绕过白名单时用 find_in(source_name, ...) 显式指定来源。
_KEY_SOURCES: dict[str, tuple[str, ...]] = {
    # 行业/板块名：只认调用方快照(extra)与板块行情(sector)，财报/资金流里的同名字段不同口径
    "industry": ("extra", "sector"),
    "行业": ("extra", "sector"),
    "所属行业": ("extra", "sector"),
    "sector_name": ("extra", "sector"),
    "板块名称": ("extra", "sector"),
    # 资金流净额（单位「元」）+ 成交额：f13 = 主力净额 / 成交额，分子分母必须同源同期。
    # quote 是实时 tick（与历史 fund 行不同期，且元/万元无元数据可校验）→ 排除；
    # 板块级「成交额」不得当作个股成交额 → 排除 sector；extra 是调用方显式给的同期快照，保留。
    "main_net_inflow": ("extra", "fund"),
    "main_inflow": ("extra", "fund"),
    "amount": ("extra", "fund"),
    "turnover_amount": ("extra", "fund"),
    "成交额": ("extra", "fund"),
}


def factor(value: Any, reason: str = "ok", quantile: float | None = None) -> FactorResult:'''),
            # (2) find() 按白名单取源 + find_in()
            ('''    def find(self, *keys: str) -> Any:
        sources = [self.extra, self.quote(), latest(self.fund_rows()),
                   latest(self.financial_rows()), latest(self.sector_rows()), self.hot_money()]
        for source in sources:
            for key in keys:
                if isinstance(source, dict) and source.get(key) not in (None, ""):
                    return source[key]
        return None''',
             '''    def _sources(self) -> list[tuple[str, dict]]:
        """各数据源按优先级列名（M20）：find / find_in 共用同一份来源顺序。

        财务/资金流走 latest_financial()/latest_fund()：带 as_of 时启用披露滞后约束（P0-6④）。
        """
        return [("extra", self.extra), ("quote", self.quote()), ("fund", self.latest_fund()),
                ("financial", self.latest_financial()), ("sector", latest(self.sector_rows())),
                ("hot_money", self.hot_money())]

    def find(self, *keys: str) -> Any:
        """按来源优先级取第一个非空值；量纲/口径有歧义的 key 由 _KEY_SOURCES 限定来源（M20）。

        原有的「来源优先于 key 顺序」语义保持不变，只对白名单内的 key 追加来源校验：
        命中源不在白名单则继续往后找，全都不是允许来源时返回 None —— 宁可缺数
        （因子记 data_missing）也不返回跨源错数量级的数。
        """
        for name, source in self._sources():
            for key in keys:
                if not isinstance(source, dict) or source.get(key) in (None, ""):
                    continue
                allowed = _KEY_SOURCES.get(key)
                if allowed is None or name in allowed:
                    return source[key]
        return None

    def find_in(self, source_name: str, *keys: str) -> Any:
        """只在指定源内取 key（M20）：跨源量纲不可比时调用方须显式指定来源。

        source_name ∈ extra / quote / fund / financial / sector / hot_money；
        来源名非法时返回 None（不静默回退到全源查找）。
        """
        for name, source in self._sources():
            if name != source_name:
                continue
            for key in keys:
                if isinstance(source, dict) and source.get(key) not in (None, ""):
                    return source[key]
        return None'''),
        ],
    },
    # ------------------------------------------------------------------ P0-6③
    {
        "id": "P0-6-3",
        "file": _IC,
        "summary": "日线复权口径校验：本地口径非 qfq 时回退远端 qfq（不丢票），远端异口径才整票弃用",
        "edits": [
            # (1) 口径常数 + P0-7 样本净化常数
            ('''# 本地日线仓库优先的覆盖容差（自然日）：首根 ≤ start+FIRST 且末根 ≥ min(end,今天)-LAST
# 才采用本地序列；新股/停牌/回补未完成一律回退远端，宁慢不错。
LOCAL_KLINE_FIRST_TOLERANCE_DAYS = 20
LOCAL_KLINE_LAST_TOLERANCE_DAYS = 10''',
             '''# 本地日线仓库优先的覆盖容差（自然日）：首根 ≤ start+FIRST 且末根 ≥ min(end,今天)-LAST
# 才采用本地序列；新股/停牌/回补未完成一律回退远端，宁慢不错。
LOCAL_KLINE_FIRST_TOLERANCE_DAYS = 20
LOCAL_KLINE_LAST_TOLERANCE_DAYS = 10
# P0-6③：日线复权口径 —— 远端 fetch_daily_kline 默认 qfq（base.py / fallback.py 签名默认，
# 调用方不传 adjust 即为 qfq）；本地仓库口径元数据由 kline_store.series_adjust 给出
# （kline_ingest 可能落 "none" 当日不复权快照）。同一票的 close 序列必须单一口径，
# 否则「目标日 close / 快照日 close - 1」在除权日会凭空多出/少掉一块，前瞻收益与 IC 全部失真。
# 校验口径不一致时分两级处理：本地不一致 → 不采用本地、回退远端 qfq 整段序列（不丢样本）；
# 远端返回的也是异口径 → 该票整票弃用：宁可缺样本，不用错样本。
KLINE_ADJUST = "qfq"
# P0-7：IC 样本口径净化 —— 脏样本同时污染 IC 与全市场分位数的可比性，宁缺勿错。
_NEW_STOCK_BARS = 5               # 新股上市前 5 个交易日无涨跌幅限制，样本特性与全市场不可比
_ST_KEYWORDS = ("ST", "退")        # 名称含 ST/*ST（风险警示）与「退」（退市整理期）→ 整票剔除'''),
            # (2) 工具函数：口径元数据读取 + 停牌/一字板判定
            ('''def _shift_date(date: str, days: int) -> str:
    """自然日平移（本地库覆盖判定用）"""
    return (datetime.strptime(str(date)[:10], "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")''',
             '''def _shift_date(date: str, days: int) -> str:
    """自然日平移（本地库覆盖判定用）"""
    return (datetime.strptime(str(date)[:10], "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")


def _local_adjust(code: str) -> str:
    """本地日线序列的复权口径元数据（P0-6③）；读不到返回 ""（未知），绝不编造口径。

    替身仓库/老库没有 series_adjust 时返回 ""，调用方按「未知不拦截」处理。
    """
    reader = getattr(kline_store, "series_adjust", None)
    if not callable(reader):
        return ""
    try:
        return str(reader(code) or "").strip()
    except Exception:  # noqa: BLE001 口径探测失败按未知处理，不影响主链路
        return ""


def _frame_adjust(frame) -> str:
    """frame 自带的口径元数据（P0-6③）：单一口径返回该值，"mixed" 表示区间内混用，读不到 ""。

    远端源目前不返回 adjust 列 → 返回 ""，按 KLINE_ADJUST 默认口径处理（不编造）。
    """
    if frame is None or not hasattr(frame, "columns") or "adjust" not in frame.columns:
        return ""
    values = {str(value or "").strip() for value in frame["adjust"].tolist()}
    values.discard("")
    if not values:
        return ""
    return values.pop() if len(values) == 1 else "mixed"


def _bar_num(bar, key: str) -> float | None:
    """bar（Series/dict）中某列的数值；缺列/NaN/非映射对象一律返回 None。"""
    try:
        return num(bar.get(key))
    except Exception:  # noqa: BLE001 缺列或非映射对象视为缺失
        return None


def _is_suspended_bar(bar, has_amount: bool, prev_close: float | None = None) -> bool:
    """停牌/占位 bar 判定（P0-7a）：量能为 0/NaN，或完全无量且收盘与前收相同。

    停牌日部分源会补一根「收盘照抄前收、volume/amount 为 0 或空」的占位行：用它算前瞻
    收益会得到 0（假样本），作为目标日又根本不可成交（forward_return 不可实现）。列缺失
    （如本地仓库 frame 无 amount）时不按该列判停牌，避免误杀正常样本。
    """
    volume = _bar_num(bar, "volume")
    if volume is not None and volume <= 0:
        return True
    if has_amount:
        amount = _bar_num(bar, "amount")
        if amount is not None and amount <= 0:
            return True
    if volume is None and prev_close is not None:
        close = _bar_num(bar, "close")
        return close is not None and close == prev_close
    return False


def _is_limit_board(bar) -> bool:
    """一字板判定（P0-7b）：全天唯一成交价（high == low == close）→ 买卖均不可成交。

    只认「high==low 且收盘就在该价」：high==low 而 close 不等于该价属占位/脏数据
    （由停牌与 NaN 规则处理），据此拦截会误杀正常样本。
    """
    high, low, close = _bar_num(bar, "high"), _bar_num(bar, "low"), _bar_num(bar, "close")
    if high is None or low is None or close is None:
        return False
    return high == low == close


def select_st_codes(universe) -> set[str]:
    """全市场快照 → ST/退市整理期代码集合（P0-7d），代码归一化口径与 select_universe_codes 一致。

    name 列缺失（部分降级快照只有 code）时返回空集：宁可少排除也不误杀，不编造名称。
    """
    if universe is None or not hasattr(universe, "columns"):
        return set()
    if "name" not in universe.columns or "code" not in universe.columns:
        return set()
    excluded = set()
    for code, name in zip(universe["code"], universe["name"]):
        text = str(name or "").upper()
        if any(keyword in text for keyword in _ST_KEYWORDS):
            excluded.add(str(code).strip().zfill(6))
    return excluded'''),
            # (3) _local_kline：口径门禁
            ('''    未覆盖而回退远端。宁慢不错：绝不用半段历史算 IC。
    """''',
             '''    未覆盖而回退远端。宁慢不错：绝不用半段历史算 IC。
    P0-6③：还要求本地口径与远端默认 KLINE_ADJUST(qfq) 一致，不一致同样不采用本地。
    """'''),
            ('''    tail = min(str(end)[:10], datetime.now().strftime("%Y-%m-%d"))
    if dates[-1] < _shift_date(tail, -LOCAL_KLINE_LAST_TOLERANCE_DAYS):
        return None
    return frame''',
             '''    tail = min(str(end)[:10], datetime.now().strftime("%Y-%m-%d"))
    if dates[-1] < _shift_date(tail, -LOCAL_KLINE_LAST_TOLERANCE_DAYS):
        return None
    # P0-6③：load_frame 只保证「区间内不混口径」，不保证与远端默认同口径 —— 本地若是
    # "none"（当日不复权快照）序列，除权日 close 会跳空，与其余走远端 qfq 的票不可比。
    # 口径不一致则不采用本地序列，由调用方回退远端 qfq（不丢样本；远端也异口径才整票弃用）。
    local_adjust = _local_adjust(code)
    if local_adjust and local_adjust != KLINE_ADJUST:
        logger.warning("本地日线口径 %s != 远端默认 %s，%s 不采用本地序列（P0-6③）",
                       local_adjust, KLINE_ADJUST, code)
        return None
    return frame'''),
            # (4) _warm_local：异口径时拒绝回写，避免把本地库搅成 mixed_adjust
            ('''    只写 qfq 口径（与 fetch_daily_kline 默认口径一致）；本地加速失败绝不影响回测结果。
    """
    try:
        rows = []''',
             '''    只写 qfq 口径（与 fetch_daily_kline 默认口径一致）；本地加速失败绝不影响回测结果。
    P0-6③：本地已存异口径序列时跳过回写 —— 否则会把本地库搅成 mixed_adjust
    （load_frame 之后直接抛 MixedAdjustError，本地加速通道整条失效）。
    """
    local_adjust = _local_adjust(code)
    if local_adjust and local_adjust != KLINE_ADJUST:
        logger.warning("本地 %s 已存 %s 口径，跳过 qfq 回写（P0-6③，避免混口径）",
                       code, local_adjust)
        return
    try:
        rows = []'''),
            # (5) _one：远端日线口径校验（本地异口径由 _local_kline 返回 None → 回退远端）
            ('''            kline = _local_kline(code, start, end)
            if kline is None:
                kline = source.fetch_daily_kline(code, start, end)
                if kline is not None and not kline.empty:
                    _warm_local(code, kline)  # 首轮回写本地，下一轮同票即走本地序列''',
             '''            # P0-6③：本地序列若是异口径（如 "none" 当日不复权快照），_local_kline 会返回 None，
            # 于是这里自动回退远端 qfq 整段序列（时间成本换正确性，不丢样本 —— kline_ingest
            # 落的当日快照口径本就是 "none"，直接整票弃用会让本地覆盖票样本量掉到 0）；
            # _warm_local 同时拒绝回写，避免把本地库搅成 mixed_adjust（那会让本地通道整体报废）。
            kline = _local_kline(code, start, end)
            if kline is None:
                kline = source.fetch_daily_kline(code, start, end)
                remote_adjust = _frame_adjust(kline)
                if remote_adjust not in ("", KLINE_ADJUST):
                    logger.warning("远端日线口径 %s != %s，%s 整票弃用（P0-6③）",
                                   remote_adjust, KLINE_ADJUST, code)
                    return
                if kline is not None and not kline.empty:
                    _warm_local(code, kline)  # 首轮回写本地，下一轮同票即走本地序列'''),
        ],
    },
    # ------------------------------------------------------------------ P0-7
    {
        "id": "P0-7",
        "file": _IC,
        "summary": "IC 样本净化：新股前 5 日/停牌占位/一字板/ST 退市整票剔除，快照日作为 as_of",
        "edits": [
            # (1) collect_month_records：可选 exclude_codes（默认 None，向后兼容）
            ('''def collect_month_records(source, month_ends: list[str], codes: list[str],
                          budget_seconds: float | None = COLLECT_BUDGET_SECONDS,
                          stats: dict | None = None) -> dict[str, list[dict]]:
    """stats 为可选出参：回填 attempted / budget_exhausted / elapsed，供调用方判断是否采满。

    采集按票并发（COLLECT_WORKERS）：只并行「票与票之间」，票内 4 次外呼顺序与产物不变；
    本地日线仓库覆盖区间时优先读本地（kline_store），否则回退远端。
    """
    records = {d[:7]: [] for d in month_ends}
    if stats is not None:
        stats["budget_exhausted"] = False
        stats["attempted"] = 0
    if not month_ends or not codes:
        return records''',
             '''def collect_month_records(source, month_ends: list[str], codes: list[str],
                          budget_seconds: float | None = COLLECT_BUDGET_SECONDS,
                          stats: dict | None = None,
                          exclude_codes=None) -> dict[str, list[dict]]:
    """stats 为可选出参：回填 attempted / budget_exhausted / elapsed，供调用方判断是否采满。

    采集按票并发（COLLECT_WORKERS）：只并行「票与票之间」，票内 4 次外呼顺序与产物不变；
    本地日线仓库覆盖区间时优先读本地（kline_store），否则回退远端。

    exclude_codes（可选，P0-7d）：整票剔除的代码集合（ST/退市整理期）。默认 None =
    不排除任何票，既有调用方与返回结构（{月份: [样本]}）完全不变。
    """
    records = {d[:7]: [] for d in month_ends}
    if stats is not None:
        stats["budget_exhausted"] = False
        stats["attempted"] = 0
    if not month_ends or not codes:
        return records
    # P0-7d：ST/退市整理期混入全市场 IC 样本会污染口径（涨跌幅限制与退市博弈特性都不同），
    # 在开票前整票剔除 —— 既不浪费外呼预算，也不产生样本。归一化口径与 select_universe_codes 一致。
    excluded = {str(code).strip().zfill(6) for code in (exclude_codes or ()) if str(code).strip()}
    if excluded:
        codes = [code for code in codes if str(code).strip().zfill(6) not in excluded]'''),
            # (2) 快照循环：脏样本剔除 + as_of 传入 adapter
            ('''            rows: list[tuple] = []
            for snapshot in month_ends:
                hits = kline.index[kline["date"].astype(str).str[:10] == snapshot].tolist()
                if not hits or hits[0] + FORWARD_DAYS >= len(kline):
                    continue
                i = hits[0]
                close, future = num(kline.iloc[i]["close"]), num(kline.iloc[i + FORWARD_DAYS]["close"])
                if close in (None, 0) or future is None:
                    continue
                history = kline.iloc[:i + 1]
                adapter = DataAdapter(source=source, code=code, kline=history, indicators={
                    "latest_close": close, "ma20": history["close"].tail(20).mean() if i >= 19 else None}, **aux)''',
             '''            rows: list[tuple] = []
            has_amount = "amount" in kline.columns
            for snapshot in month_ends:
                hits = kline.index[kline["date"].astype(str).str[:10] == snapshot].tolist()
                if not hits or hits[0] + FORWARD_DAYS >= len(kline):
                    continue
                i = hits[0]
                # P0-7c：上市初期（序列前 _NEW_STOCK_BARS 根）无涨跌幅限制，样本特性与全市场不可比
                if i < _NEW_STOCK_BARS:
                    continue
                bar, target = kline.iloc[i], kline.iloc[i + FORWARD_DAYS]
                # P0-7a/b：快照 bar 与目标 bar 都必须可成交 —— 停牌占位行/一字板任一命中即丢
                # 该样本；目标日不可成交时前瞻收益根本不可实现，留着就是假样本（会拉低/抬高 IC）。
                if _is_suspended_bar(bar, has_amount, _bar_num(kline.iloc[i - 1], "close")):
                    continue
                if _is_limit_board(bar):
                    continue
                if _is_suspended_bar(target, has_amount,
                                     _bar_num(kline.iloc[i + FORWARD_DAYS - 1], "close")):
                    continue
                if _is_limit_board(target):
                    continue
                close, future = num(kline.iloc[i]["close"]), num(kline.iloc[i + FORWARD_DAYS]["close"])
                if close in (None, 0) or future is None:
                    continue
                history = kline.iloc[:i + 1]
                # P0-6④：把快照日作为 as_of 传给 adapter —— 财报/资金流取用叠加披露滞后约束，
                # 只能用「当时市场已看到」的那一期；不传 as_of 的线上路径行为不变。
                adapter = DataAdapter(source=source, code=code, kline=history, indicators={
                    "latest_close": close, "ma20": history["close"].tail(20).mean() if i >= 19 else None},
                    extra={"as_of": snapshot}, **aux)'''),
            # (3) 作业：全市场快照 → ST 代码集合传给采集
            ('''        ends = _month_ends(source.fetch_trade_calendar(), months)
        codes = select_universe_codes(source.fetch_spot_universe())
        records = collect_month_records(source, ends, codes, COLLECT_BUDGET_SECONDS, stats=stats)''',
             '''        ends = _month_ends(source.fetch_trade_calendar(), months)
        universe = source.fetch_spot_universe()
        codes = select_universe_codes(universe)
        # P0-7d：ST/退市整理期整票剔除出 IC 样本（全市场分位数侧不属本仓库，见交付报告）
        records = collect_month_records(source, ends, codes, COLLECT_BUDGET_SECONDS, stats=stats,
                                        exclude_codes=select_st_codes(universe))'''),
        ],
    },
]
