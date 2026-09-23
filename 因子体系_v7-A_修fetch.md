# 因子体系 v7-A：单目标 1 = 修 fetch_spot_universe（30 行）

## 任务

修 `run_factor_ic_once.py` 落库 0 条的根因。`factor_ic.py:155-160` 调用 `datasource.fetch_spot_universe()` 返回空 → 0 票 × 0 月 = 0 记录。

## 修复

```bash
grep -n "def fetch_" backend/app/datasource/*.py | head -20
grep -n "list_active_stocks\|list_stocks\|all_codes" backend/app/db/repo.py | head -5
```

按 grep 结果：
- 如有正确方法（`fetch_stock_list` / `list_codes` 等）→ 改 `factor_ic.py:155-160` 用正确方法
- 如 datasource 无正确方法 → 加 fallback：调 `repo.list_active_stocks()` 取股票代码 list

## 验证

```bash
/d/self/.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, r'D:\self\backend')
from app.datasource import get_datasource
s = get_datasource()
uni = s.fetch_spot_universe()
print('universe:', len(uni) if uni is not None else 0)
"
```

期望：`universe: ≥ 100`（A 股至少几千只票）

## 报告

```
① 改了哪 1-2 个文件（path:line）
② universe 实际数量
③ 验证命令输出
```

## 启动

```bash
codex --approval-mode auto-edit --no-auto-commits --cd D:\self
```

开场白：执行 v7-A，单目标修 fetch_spot_universe。**禁止修 whitespace**。完成 ≤ 5 分钟。
