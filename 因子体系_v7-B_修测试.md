# 因子体系 v7-B：单目标 2 = 修 1 例 test fixture（30 行）

## 任务

修 `test_end_to_end.py` 中 1 个 fixture 错误（7 passed 1 failed）。失败原因：`validate_candidates.py` 测试替身 `universe["code"]` 类型不符。

## 修复

```bash
grep -n "universe\|def test_validate" backend/tests/test_end_to_end.py
```

修法：把 fixture 中 `universe` 改成 `validate_candidates` 实际期望的格式（list of str / DataFrame / 真实 mock）。

## 验证

```bash
cd /d/self/backend && /d/self/.venv/Scripts/python.exe -m pytest tests/test_end_to_end.py -q
```

期望：`8 passed, 0 failed`

## 报告

```
① 改了哪 1-2 行（path:line）
② pytest 8 passed 0 failed
```

## 启动

开场白：执行 v7-B，单目标修 1 例 fixture。**禁止修 whitespace**。完成 ≤ 3 分钟。
