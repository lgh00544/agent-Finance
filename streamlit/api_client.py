"""
Streamlit → backend API 客户端
面板只做展示与人工数据录入，不内置任何二次判断逻辑。
"""
import os

import requests

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def _get(path: str, params: dict | None = None) -> dict | list:
    resp = requests.get(f"{API_BASE}{path}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json: dict | None = None) -> dict | list:
    resp = requests.post(f"{API_BASE}{path}", json=json or {}, timeout=600)
    resp.raise_for_status()
    return resp.json()


def _put(path: str, json: dict | None = None) -> dict | list:
    resp = requests.put(f"{API_BASE}{path}", json=json or {}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def health() -> dict:
    return _get("/api/health")


# ================= 后台异步任务（提交即返回 + 状态查询 + 重试） =================
def submit_task(kind: str, params: dict | None = None) -> dict:
    """提交后台任务，立即返回 task_id（不阻塞页面，可切换页面继续操作）"""
    return _post("/api/tasks/submit", {"kind": kind, "params": params or {}})


def recent_tasks(limit: int = 8) -> list:
    """最近后台任务（最新在前，含状态/提交时间/失败原因）"""
    return _get("/api/tasks/recent", {"limit": limit})


def task_detail(tid: str) -> dict:
    """任务详情（状态/结果/失败原因）"""
    return _get(f"/api/tasks/{tid}")


def retry_task(tid: str) -> dict:
    """失败任务一键重试（复用原任务ID）"""
    return _post(f"/api/tasks/{tid}/retry")


def batch_import_knowledge(items: list[dict]) -> dict:
    """批量导入私有知识条目（异步提交，逐条落库）"""
    return _post("/api/knowledge/batch-import", {"items": items})


def run_discover() -> dict:
    return _post("/api/jobs/discover/run")


def job_status() -> dict:
    return _get("/api/jobs/status")


def system_status() -> dict:
    return _get("/api/system/status")


def dashboard() -> dict:
    """首页看板聚合：一次请求并行返回系统状态/LLM统计/市况/持仓信号/候选评分/复盘建议
    （单模块失败仅标注 error，不阻塞整体）"""
    return _get("/api/dashboard")


def llm_stats() -> dict:
    """LLM 运行统计（当日累计：请求次数/缓存命中 token/命中率/模型分布）"""
    return _get("/api/llm/stats")


def datasource_stats() -> dict:
    """行情数据源状态（当日累计：主源调用/失败/降级次数、成功率、当前源状态）"""
    return _get("/api/datasource/stats")


def market_condition() -> dict | None:
    """当日市况评分（v2.0 前置步骤：总分/档位/候选池上限/五维/综述）"""
    return _get("/api/market-condition")


def market_intel(date: str | None = None) -> dict:
    """市场研判底座（指定日期或最新一日；不存在时后端返回 404 → HTTPError）"""
    params = {"date": date} if date else {}
    return _get("/api/market_intel", params)


def market_intel_dates(limit: int = 30) -> list[str]:
    """已生成市场研判的日期列表（最新在前）。
    后端返回裸数组（React 兼容；原包裹 {"dates": [...]} 已废弃）"""
    return _get("/api/market_intel/dates", {"limit": limit}) or []


def market_indices() -> dict:
    """三大指数实时行情（上证指数/深证成指/创业板指 + 更新时间；失败含 error 标注）"""
    return _get("/api/market/indices")


def index_history(days: int = 90) -> dict:
    """三大指数日线历史（只读，近 N 天）：change_pct 已按收盘价回算；失败 items 空 + error 标注"""
    return _get("/api/market/indices/history", {"days": days})


def market_hot_sectors() -> dict:
    """今日涨幅前 5 行业板块 + 领涨龙头（代码+名称）+ 更新时间"""
    return _get("/api/market/hot-sectors")


def account_summary() -> dict:
    """账户核心资产摘要（双数据路径：有 OCR 账户基准用券商值，否则按总资金设定估算）"""
    return _get("/api/account/summary")


def save_account_baseline(body: dict) -> dict:
    """保存账户基准（OCR 识别结果经人工确认后调用）"""
    return _post("/api/account/baseline", body)


def candidates(date: str | None = None, limit: int | None = None) -> list:
    params = {"date": date} if date else {}
    if limit is not None:
        params["limit"] = limit
    return _get("/api/candidates", params or None)


def candidate_dates(limit: int = 30) -> list:
    """候选池可选日期（去重降序，最新在前）：默认只加载最新一天，切换日期按需查询。
    后端返回裸数组（React 兼容；原包裹 {"dates": [...]} 已废弃）"""
    return _get("/api/candidates/dates", {"limit": limit}) or []


def candidate_tradeable(date: str | None = None, limit: int = 200) -> dict:
    """当日可建仓判定视图（只读）：{date, count, plan_candidate_count, total, items}
    count=可建仓数（0 也明确返回），plan_candidate_count=可自动生成建仓计划的标的数"""
    params = {"limit": limit}
    if date:
        params["date"] = date
    return _get("/api/candidates/tradeable", params)


def candidate_concentration(date: str | None = None) -> dict:
    """候选行业集中度（只读 detail.enriched.industry）：
    {total, groups, max_concentration, max_industry, coverage}；coverage<50% 前端不展示集中度"""
    params = {}
    if date:
        params["date"] = date
    return _get("/api/candidate/concentration", params or None)


def traces(code: str | None = None, date: str | None = None,
           module: str | None = None, limit: int = 50) -> list:
    """推理留痕轻量列表（不含长文本，毫秒级；详情按需单查）"""
    params = {}
    if code:
        params["code"] = code
    if date:
        params["date"] = date
    if module:
        params["module"] = module
    if limit is not None:
        params["limit"] = limit
    return _get("/api/traces", params or None)


def trace_detail(trace_id: int) -> dict:
    """推理留痕完整详情（结论卡 + 分层推理全文）"""
    return _get(f"/api/traces/{trace_id}")


def scores(code: str | None = None, date: str | None = None, limit: int | None = None) -> list:
    params = {}
    if code:
        params["code"] = code
    if date:
        params["date"] = date
    if limit is not None:
        params["limit"] = limit
    return _get("/api/scores", params or None)


def trigger_score(code: str) -> dict:
    return _post(f"/api/score/{code}", {"stock_code": code})


def stock_names(codes: list[str]) -> dict:
    """批量补名（只读，不写库）：返回 {code: name}，查不到的名称不出现"""
    if not codes:
        return {}
    return _get("/api/stocks/names", {"codes": ",".join(codes)})


def plans(code: str | None = None, limit: int | None = None) -> list:
    params = {"code": code} if code else {}
    if limit is not None:
        params["limit"] = limit
    return _get("/api/positions", params or None)


def create_plan(code: str, name: str = "") -> dict:
    return _post("/api/positions/plan", {"stock_code": code, "stock_name": name})


def holdings(status: str | None = None) -> list:
    return _get("/api/holdings", {"status": status} if status else None)


def holding_quotes() -> dict:
    """持仓列表视图：实时行情 + 参考止损/止盈 + 目标仓位%（只读；去重合并由前端展示层完成）"""
    return _get("/api/holdings/quotes")


def add_holding(body: dict) -> dict:
    return _post("/api/holdings", body)


def ocr_status() -> dict:
    """OCR 功能状态（是否启用/可用），前端据此提示"""
    return _get("/api/ocr/status")


def ocr_holding(image_bytes: bytes, filename: str) -> dict:
    """上传持仓截图 → OCR 识别持仓字段（仅回填表单，不直接入库）"""
    resp = requests.post(f"{API_BASE}/api/ocr/holding",
                         files={"file": (filename, image_bytes, "image/png")}, timeout=180)
    resp.raise_for_status()
    return resp.json()


def exit_holding(hid: int, body: dict) -> dict:
    return _post(f"/api/holdings/{hid}/exit", body)


def holding_add(hid: int, body: dict) -> dict:
    """手动加仓：加权成本重算 + C3 止损联动 + 流水留痕"""
    return _post(f"/api/holdings/{hid}/add", body)


def holding_cost(hid: int, body: dict) -> dict:
    """手动成本修正：cost/C3 联动重算 + adjust 流水留痕（原因必填）"""
    return _post(f"/api/holdings/{hid}/cost", body)


def holding_trades(hid: int) -> list:
    """持仓操作流水（最新在前）：加仓/减仓/清仓/成本修正 可追溯"""
    return _get(f"/api/holdings/{hid}/trades")


def monitor_holding(hid: int) -> dict:
    return _post(f"/api/holdings/{hid}/monitor")


def sell_decision(hid: int) -> dict:
    """生成一次卖出决策（SellAgent；仅供参考，卖出人工执行）"""
    return _post(f"/api/holdings/{hid}/sell-decision")


def sell_decisions(hid: int) -> list:
    return _get(f"/api/holdings/{hid}/sell-decisions")


def agent_suggestions(status: str | None = None, target_agent: str | None = None) -> list:
    params = {}
    if status:
        params["status"] = status
    if target_agent:
        params["target_agent"] = target_agent
    return _get("/api/agent-suggestions", params or None)


def approve_suggestion(sid: int) -> dict:
    return _post(f"/api/agent-suggestions/{sid}/approve")


def adopt_suggestion(sid: int, confirm: bool = False) -> dict:
    """一键采纳自动落地（规则类建议）：硬规则需 confirm=True 二次确认"""
    return _post(f"/api/agent-suggestions/{sid}/adopt", {"confirm": confirm})


def reject_suggestion(sid: int, reason: str = "") -> dict:
    return _post(f"/api/agent-suggestions/{sid}/reject", {"reason": reason} if reason else None)


def rule_changes(status: str | None = None, target_agent: str | None = None,
                 suggestion_id: int | None = None) -> list:
    """规则变更记录（一键采纳/回滚全量留痕，时间倒序）"""
    params = {}
    if status:
        params["status"] = status
    if target_agent:
        params["target_agent"] = target_agent
    if suggestion_id is not None:
        params["suggestion_id"] = suggestion_id
    return _get("/api/rule-changes", params or None)


def rollback_rule_change(rid: int, reason: str) -> dict:
    return _post(f"/api/rule-changes/{rid}/rollback", {"reason": reason})


# ================= 候选池 T+N 验证（选股效果闭环） =================
def track_verify_list(select_date: str = "", rating: str = "", status: str = "",
                      limit: int = 200) -> list:
    """追踪验证行列表（status: all/tracking/finished）"""
    params = {}
    if select_date:
        params["select_date"] = select_date
    if rating:
        params["rating"] = rating
    if status and status != "all":
        params["status"] = status
    if limit != 200:
        params["limit"] = limit
    return _get("/api/track/verify/list", params or None)


def track_verify_dates(limit: int = 30) -> list:
    """追踪验证可选日期（去重降序）"""
    return _get("/api/track/verify/dates", {"limit": limit})


def track_verify_stats(period: str = "t5") -> dict:
    """周期统计（从已存验证行纯计算；period: t3/t5/t10）"""
    return _get("/api/track/verify/stats", {"period": period})


def run_track_verify(backfill: bool = False) -> dict:
    """手动触发候选 T+N 验证（backfill=True 历史回填，幂等）"""
    return _post("/api/track/verify/run", {"backfill": backfill})


def run_track_suggest() -> dict:
    """手动触发选股验证建议生成（LLM 为主 + 模板兜底，来源标记）"""
    return _post("/api/track/verify/suggest")


def knowledge() -> list:
    return _get("/api/knowledge")


def add_knowledge(title: str, content: str, agent_tag: str) -> dict:
    return _post("/api/knowledge", {"title": title, "content": content, "agent_tag": agent_tag})


def delete_knowledge(kid: int) -> dict:
    return _post(f"/api/knowledge/{kid}/delete")


def alerts(limit: int | None = None) -> list:
    return _get("/api/alerts", {"limit": limit} if limit is not None else None)


def reviews(code: str | None = None, limit: int | None = None) -> list:
    params = {"code": code} if code else {}
    if limit is not None:
        params["limit"] = limit
    return _get("/api/reviews", params or None)


def take_profit_plan(force: bool = False) -> dict:
    """全部持仓的分档止盈/仓位管理计划（与持仓监控页同源，纯计算零 LLM）"""
    return _get("/api/holdings/take-profit-plan",
                {"force": "1"} if force else None)


# ================= 游资追踪 =================

def hot_money_profiles(q: str = "", tier: str = "") -> list:
    """游资档案列表（名称/席位/梯队/风格/擅长题材/5日胜率）；q=模糊搜索、tier=档位过滤"""
    params = {}
    if q:
        params["q"] = q
    if tier:
        params["tier"] = tier
    return _get("/api/hot-money/profiles", params or None)


def hot_money_flows(date: str | None = None, code: str | None = None,
                    lhb_type: str = "1d", limit: int = 500) -> list:
    """龙虎榜原始流水（按日/标的/口径筛选）"""
    params = {"limit": limit}
    if date:
        params["date"] = date
    if code:
        params["code"] = code
    if lhb_type:
        params["lhb_type"] = lhb_type
    return _get("/api/hot-money/flows", params)


def hot_money_traces(code: str | None = None, limit: int = 50) -> list:
    """游资研判留痕（source_module='hot_money'）"""
    params = {"limit": limit}
    if code:
        params["code"] = code
    return _get("/api/hot-money/traces", params)


def hot_money_winrate_iterate() -> dict:
    """触发游资胜率迭代（只生成建议 pending + 统计事实落库，人工审核后生效）"""
    return _post("/api/hot-money/win-rate-iteration")


def hot_money_tier_apply(suggestion_id: int) -> dict:
    """人工审核确认后应用游资档位建议（仅 approved 可执行）"""
    return _post("/api/hot-money/tier/apply", {"suggestion_id": suggestion_id})


def adopt_review(rid: int) -> dict:
    return _post(f"/api/reviews/{rid}/adopt")


def reject_review(rid: int, reason: str) -> dict:
    return _post(f"/api/reviews/{rid}/reject", {"reason": reason})


def get_profile() -> dict:
    return _get("/api/profile")


def put_profile(content: dict) -> dict:
    return _put("/api/profile", {"content": content})


def export_profile() -> dict:
    return _get("/api/profile/export")


def import_profile(content: dict) -> dict:
    return _post("/api/profile/import", {"content": content})


# ================= Agent 专属对话（提问答疑 / 规则调教 / 多模态学习） =================
def chat_agents() -> list:
    """六 Agent 对话元信息（名称/职责范围/知识库来源）"""
    return _get("/api/agent-chat/agents")


def chat_history(agent: str, limit: int = 50, message_type: str | None = None) -> list:
    """某 Agent 的对话历史（最新在前）；message_type 可选过滤（batch=批量验证对话）"""
    params = {"agent": agent, "limit": limit}
    if message_type:
        params["message_type"] = message_type
    return _get("/api/agent-chat/history", params)


def batch_ask(scope: str, codes: list, question: str, date: str = "") -> dict:
    """候选池批量验证对话（异步任务，返回 task_id）：
    按范围（all/tradeable/A/B/C/manual）注入候选上下文 →「总-分」回答 + 调整建议"""
    return _post("/api/agent-chat/batch-ask",
                 {"scope": scope, "codes": codes, "question": question, "date": date})


def apply_batch_adjust(batch_id: int) -> dict:
    """确认生效：将批量对话调整方案写入 candidate_adjust（覆盖展示层判定，可回滚）"""
    return _post("/api/agent-chat/batch-adjust/apply", {"batch_id": batch_id})


def rollback_batch_adjust(batch_id: int, reason: str = "") -> dict:
    """回滚：删除本次覆盖恢复原判定"""
    return _post(f"/api/agent-chat/batch-adjust/{batch_id}/rollback", {"reason": reason})


def chat_ask(agent: str, question: str) -> dict:
    """文字提问（异步任务，返回 task_id；结果含答案/信心度/依据来源）"""
    return _post("/api/agent-chat/ask", {"agent": agent, "question": question})


def chat_rule(agent: str, proposal: str) -> dict:
    """规则调教校验（异步任务；结论 采纳/部分采纳/维持原规则，采纳自动沉淀知识库）"""
    return _post("/api/agent-chat/rules", {"agent": agent, "proposal": proposal})


def chat_learn(agent: str, image_bytes: bytes, filename: str, description: str = "") -> dict:
    """多模态上传学习（异步；结果含确认摘要与建议知识点，确认后才落库）。
    description 为可选辅助文本描述（≤500字，图片为主、文字为辅）"""
    resp = requests.post(f"{API_BASE}/api/agent-chat/learn",
                         params={"agent": agent},
                         files={"file": (filename, image_bytes)},
                         data={"description": description}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def chat_learn_confirm(agent: str, entries: list[dict]) -> dict:
    """确认多模态学习结果：知识点（可含修正后的标签）写入对应 Agent 知识库"""
    return _post("/api/agent-chat/learn/confirm", {"agent": agent, "entries": entries})


# ================= 经验沉淀闭环（自动识别 → 分层审核 → 检索注入） =================
class ConflictError(Exception):
    """后端 409 冲突（已有同类任务 / 状态不允许操作）；页面捕获后提示而非报错"""


def get_experience_pending(status: str | None = None, stage: str | None = None,
                           limit: int = 50) -> list:
    """M1 沉淀队列（只读看板；pending/processing/done 分类计数）"""
    params = {"limit": limit}
    if status:
        params["status"] = status
    if stage:
        params["stage"] = stage
    return _get("/api/experience/pending", params)


def run_experience_worker() -> dict:
    """M1 立即触发识别（异步后台任务）；同类型活跃时后端 409 → 抛 ConflictError"""
    try:
        return _post("/api/experience/worker/run")
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 409:
            raise ConflictError("已有识别任务执行中，请等待其完成后重试") from exc
        raise


def get_experience_list(status: str | None = None, stage: str | None = None,
                        auto_merged: int | None = None, limit: int = 100) -> list:
    """经验库列表（按状态/阶段/自动合并筛选；M2 Digest 取 status=pending_review）"""
    params = {"limit": limit}
    if status:
        params["status"] = status
    if stage:
        params["stage"] = stage
    if auto_merged is not None:
        params["auto_merged"] = auto_merged
    return _get("/api/experience/list", params)


def search_experience(stage: str | None = None, query: str | None = None, k: int = 50) -> list:
    """经验检索（参数名是 query 不是 q；仅返回 active；k=50 保证够用）"""
    params = {"k": k}
    if stage:
        params["stage"] = stage
    if query:
        params["query"] = query
    return _get("/api/experience/search", params)


def get_experience_config() -> dict:
    """M5 设置读取（返回值全为字符串，页面侧需 float()/int()/bool 转换）"""
    return _get("/api/experience/config")


def set_experience_config(config: dict) -> dict:
    """M5 设置写入（key-value 热加载，无需重启；key 须为已知配置项）"""
    return _post("/api/experience/config", {"config": config})


def get_experience_detail(eid: int) -> dict:
    """单条经验（含 source_summary / source_task_id）"""
    return _get(f"/api/experience/{eid}")


def review_experience(eid: int, action: str, note: str = "") -> dict:
    """M2/M3 审核：approve→active / reject→rejected（驳回必填理由）。
    非 pending_review→409、驳回无理由→400，均抛 ConflictError"""
    try:
        return _post(f"/api/experience/{eid}/review", {"action": action, "note": note})
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (400, 409):
            detail = ""
            try:
                detail = exc.response.json().get("detail", "")
            except Exception:  # noqa: BLE001
                pass
            raise ConflictError(detail or "操作不允许（状态或参数不符）") from exc
        raise


def rollback_experience(eid: int) -> dict:
    """M4 回滚（仅 active 且 auto_merged=1 可回滚；否则 409 → ConflictError）"""
    try:
        return _post(f"/api/experience/{eid}/rollback")
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 409:
            detail = ""
            try:
                detail = exc.response.json().get("detail", "")
            except Exception:  # noqa: BLE001
                pass
            raise ConflictError(detail or "仅已生效且自动合并的经验可回滚") from exc
        raise
