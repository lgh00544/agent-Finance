"""ReAct 智能体研判 PoC: 把 ScoreAgent 的单发调用换成 观察→调工具→推理 循环。

用法:  .venv\\Scripts\\python backend\\scripts\\agentic_poc.py [--code 600519] [--rounds 8] [--name 贵州茅台]
只新增文件, 不改既有链路; 数据源/LLM 均由工具按需拉取。
"""
import argparse
import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_BACKEND_DIR.parent))
os.environ.setdefault("APP_ENV", "dev")

# 控制台输出统一 UTF-8, 避免 Windows GBK 下 emoji/中文报错
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.agents.agentic_tools import TOOLS, TOOL_FUNCS  # noqa: E402
from app.agents.schemas import ScoreOutput  # noqa: E402
from app.llm.agentic import run_agentic_judge  # noqa: E402

SYSTEM_PROMPT = """你是 A 股个股评分研判 Agent(只读, 禁止任何写入/下单操作)。
你的任务: 对给定股票完成六因子透明评分, 并输出严格 JSON。
方法: 先用只读工具(get_quote / get_daily_kline / get_news / get_financial / get_fund_flow / search_knowledge)
核实行情、K线、新闻、财务、资金流与私有经验; 证据不足就继续查, 缺口要如实说明; 证据充分后输出最终 JSON(不要再调用工具)。

输出契约(严格 JSON, 孤对象, 无任何前后缀文字):
- factors: 恰好六项, 每项 {factor: 动量|催化|估值|主线契合|资金面|基本面质量, score: 0-10整数, reason: 引用具体数据的中文依据30-80字, signal: 看多|中性|看空}
- score: 综合得分 0-100 整数; grade: A|B|C; potential_flag: 当 催化≥7 且 动量≤4 时为 true
- cross_validation_note: 与选股逻辑交叉验证的一段结论
- risk_list: 风险清单(数组); final_advice: 「综合评估:N/6因子看多,总分XX分(X级),结论,止损-8%,主要风险…」
- stock_code / stock_name 原样返回"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="600519")
    ap.add_argument("--name", default="贵州茅台")
    ap.add_argument("--rounds", type=int, default=8)
    args = ap.parse_args()

    user_prompt = (
        f"请对股票 {args.name}({args.code}) 做六因子透明评分。\n"
        f"先用工具核实行情/日K/新闻/财务/资金流/历史经验; 数据充分后再输出最终 JSON。"
    )
    result, log = run_agentic_judge(SYSTEM_PROMPT, user_prompt, ScoreOutput,
                                    TOOLS, TOOL_FUNCS, max_rounds=args.rounds)

    print("=" * 70)
    print(f"对象: {args.name}({args.code})   轮数: {log.get('rounds', 0)}   "
          f"ok={log.get('ok', False)}  error={log.get('error', '')}")
    print("-" * 70)
    for step in log.get("trace", []):
        kind = step.get("kind")
        if kind == "thinking":
            print(f"  [思考] {step.get('text', '')[:200]}")
        elif kind == "tool":
            print(f"  [工具] {step.get('tool')}({step.get('args')})\n"
                  f"         -> {step.get('result', '')[:260]}")
        else:
            print(f"  [最终] {step.get('content', '')[:300]}")
    print("=" * 70)
    if result is not None:
        print("✅ 校验通过:", result.model_dump_json(indent=2, ensure_ascii=False))
    else:
        print("❌ 未产出合法结果")


if __name__ == "__main__":
    main()