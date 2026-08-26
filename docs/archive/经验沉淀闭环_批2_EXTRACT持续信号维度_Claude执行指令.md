# 经验沉淀闭环 · 批 2(EXTRACT_SYSTEM 持续信号维度)— Claude Code 执行指令

## 〇 元信息
执行者:Claude Code。决策人:sir。范围:**EXTRACT_SYSTEM 加"持续信号"判定规则**,让 LLM 看到合并后 count≥3 的重复信号 → 直接 worth=True 沉淀。原则:不改 schema、不动 Worker、不动前端、改 ≤ 30 行。

## 一 目标
**给 EXTRACT_SYSTEM 加一条"持续信号"维度** —— 解决"290 条重复信号全标 worth=False 丢"的根因 B(占 30%)。

**具体目标**:
- 看到 `artifacts_ref.count >= 3` → `worth=True` + 标 `tags=["持续信号", stock_code]` + body 含 count 数字
- 规则加在 EXTRACT_SYSTEM 末尾,不影响其他规则
- 不动 `ExperienceDraft` schema(stage/impact/confidence 已够用)
- 不动 Worker / 前端 / M5

## 二 架构约束
- **1 文件 + 1 测试**:
  - `agent_prompts/experience_prompt.py:7-23` EXTRACT_SYSTEM 加 1 规则段(5-8 行)
  - `tests/test_extract_prompt_持续信号.py` 新建,3 测试
- **不引新库**
- **不动 schema**:`ExperienceDraft` 已含 worth/title/body/stage/tags/impact/confidence/reason

## 三 规则

### 3.1 新增规则(EXTRACT_SYSTEM 末尾追加)

```
- 若 artifacts_ref 含 count 字段且 count ≥ 3:
  - worth=true（持续信号本身即经验,价值高于单次观测）
  - title 必须含「持续信号」+ 标的代码 + 信号类型
  - body 必须含「在 N 次观察中持续出现 M 次」+ 该信号的具体含义
  - tags 必须包含 "持续信号" + stock_code（便于按票检索）
  - impact=low（持续信号是观测类,非规则变更）
  - confidence=0.5~0.7（持续信号本身可信,但"是否有用"待验证）
```

### 3.2 3 个测试(必须全过)

1. **常规 worth=False 不变**:常规信号 count=1 → LLM 仍可标 worth=False(测试用 mock 验证 prompt 不强加)
2. **常规 worth=True 不变**:常规信号含真实经验 → LLM 仍可标 worth=True
3. **持续信号维度生效**:mock artifacts_ref count=5 → prompt 命中"持续信号"规则段,可手动验 LLM 输出形态

> 测试方法:`assert "持续信号" in EXTRACT_SYSTEM` + `assert "count >= 3" or "count ≥ 3" in EXTRACT_SYSTEM` + 单元级不调 LLM(LLM 输出形态留手动验证)。

## 四 执行顺序
1. 读 `agent_prompts/experience_prompt.py` 全文
2. 在 EXTRACT_SYSTEM 末尾(第 23 行 `worth=false。"""` 前)加"持续信号"规则段
3. 新建 `tests/test_extract_prompt_持续信号.py`,3 测试
4. `cd backend && .venv/Scripts/python.exe -m pytest tests/test_extract_prompt_持续信号.py -q` → 3 passed
5. 跑回归:`test_pending_dedup` 5 passed 不破

## 五 验证清单
- [ ] EXTRACT_SYSTEM 含「持续信号」关键字
- [ ] EXTRACT_SYSTEM 含 `count >= 3`(或 `count ≥ 3`)判定
- [ ] 规则提到 tags 必须含「持续信号」
- [ ] 3 测试全过
- [ ] test_pending_dedup 仍 5 passed
- [ ] Worker 行为不变(不动 services/experience_worker.py)

## 六 红线
1. **绝不动 schema**(ExperienceDraft 不动)
2. **绝不动 Worker**(services/experience_worker.py 不动)
3. **绝不动前端**
4. **绝不删旧规则** —— 只在末尾追加"持续信号"段
5. **绝不引入新字段** —— 复用 tags + body
6. 改动 ≤ 30 行(超出停下报 sir)

**Claude 端省 token 约束**:①不复读本提示词(只 grep path:line)②只动 1 个 prompt 文件 + 1 新测试 ③不写大段注释(docstring≤3行)④复用现有 EXTRACT_SYSTEM 字符串,只 `+=` 追加段 ⑤测试不超 3 个 ⑥报告 ≤ 8 行(改了哪些文件/3 测试结果)。
