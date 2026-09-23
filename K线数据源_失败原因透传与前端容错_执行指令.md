# K 线数据源·失败原因透传 + 前端容错_执行指令

## 背景（已独立诊断确认）
- 现象：`GET /api/kline/{code}` 偶发返回 `klines: []`，耗时 18-45s；复测已恢复（600036/601398 各 23 行），属**上游间歇失败**。
- 根因链：
  1. 主源东财 `push2his.eastmoney.com` → `ProxyError: Unable to connect to proxy`（本机沙箱代理 `127.0.0.1:65270` 对东财隧道不通）
  2. 备源新浪成功但慢（12-45s）
  3. `backend/app/datasource/akshare_source.py:434` 空结果不缓存 → 每次点击重跑全链路
  4. `backend/app/db/repo.py:2527` `except Exception: return []` 裸吞异常 → 前端只显示「K线缺失」，无法区分原因

## 目标
让"上游挂了"和"该股真无数据"在前端可区分，并降低连点代价。**只做透传与体验，不改采集刚性逻辑。**

## Part 1 代码改动

| 文件 | 改什么 |
|---|---|
| `backend/app/db/repo.py:2513-2528` | 保留 `fetch_daily_kline(code,start,end) -> list[dict]` 签名与行为不变（其他调用方零影响）；**新增** `fetch_daily_kline_detail(code,start,end) -> dict`，返回 `{"rows": [...], "status": "ok"\|"empty"\|"upstream_error", "detail": str}`。`upstream_error` 时把异常类名+摘要写入 `detail`（≤200 字）。原函数内部改为委托新函数取 `rows` |
| `backend/app/api/routes.py:2324-2329` | `/kline/{stock_code}` 返回**只增字段**：`{"code", "klines", "status", "detail"}`。缺 start/end 时 `status="empty"`。`klines` 与既有字段结构**逐字不变** |
| `web/src/components/charts/KlineChart.tsx` | 读 `status`：`upstream_error` → 提示「上游行情源暂时不可用（东财/新浪均失败），已重试仍失败，请稍后点重试」+ 保留重试按钮；`empty` → 「该股在所选窗口内无交易日数据」。给 query 加 `staleTime: 5 * 60_000` 避免组件重挂载立即重跑；`retry: 0` 保持 |

## Part 2 只诊断（不改代码，输出报告）
1. 检查后端服务进程 env 是否含 `HTTP_PROXY/HTTPS_PROXY`（沙箱注入的 `127.0.0.1:6527x`）；若有，实测加 `NO_PROXY=push2his.eastmoney.com,hq.sinajs.cn,*.sinajs.cn,*.eastmoney.com` 后东财主源是否恢复可达、单次耗时降到多少。
2. 用 `.venv/Scripts/python.exe` 直调 `ak.stock_zh_a_hist` / `ak.stock_zh_a_daily` 各 3 次，记录成功/失败/耗时，判断是否为**沙箱代理特有**（真实终端启动后端是否无此问题）。
3. 报告结论：是"仅本机沙箱代理所致"还是"数据源接口本身不稳"，给出是否值得设置 `NO_PROXY` 的建议。

## 红线
1. **不动** `akshare_source.py` 的 `_fetch` / `_call_with_retry` / 断路器 / 限流 / 超时设置 / 主备顺序 —— 数据采集刚性逻辑
2. **不动**交易规则、研判口径、评分阈值、任何写入路径
3. `/kline` 既有响应字段（`code`/`klines` 及每条 `date/open/high/low/close/volume`）**逐字不变**，只新增 `status`/`detail`
4. `KlineChart` 的 `enabled: !!code && !!anchorDate` 语义不变；**不伪造**数据、不用 0 或占位行代替缺失
5. 改动 ≤ 90 行；不新增文件；不写测试（Part 2 除外，报告即可）

## 验收
1. 上游正常时：`/api/kline/600036?start=2026-08-15&end=2026-09-16` 返回 23 行且 `status="ok"`
2. 上游失败时：返回 `status="upstream_error"` + `detail` 非空，`klines: []`；前端显示"上游行情源暂时不可用"而非"K线缺失"
3. 窗口内无交易日：`status="empty"`，前端显示"该股在所选窗口内无交易日数据"
4. 三处 K 线入口（候选池/持仓详情/复盘）与模拟持仓 K 线 Drawer 均不回归
5. Part 2 报告 ≥ 3 条实测数据（成功/失败/耗时），结论明确
