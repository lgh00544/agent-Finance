# 同花顺 Cookie 一键续期 · Codex 执行指令

> §0 元信息
> 执行：Codex  ｜  决策：sir  ｜  原则：1 文件 1 任务 1 commit，分 3 段（后端 1 / 前端 1 / 文档 1）
> 关联方案：`D:\self\同花顺Cookie一键续期_方案.md`（9 段：现状 / 目标 / 4 级 fallback / 后端 4 文件 / 前端 1 文件 / 验收 / 批次 / 不动 / 引用）
> 关联文件：ths_pnl.py:63 load_cookie / OverviewPage.tsx:86-95 卡片 / jobs.py:1027-1039 cron

---

## §一 目标（4 段零）

| # | 段 | 现状 | 目标 |
|---|---|---|---|
| 0 | DSH 凭证失效 | Sir Chrome 登录了同花顺账本，**sir 自己的 cookie 跟 DSH 不互通** | 后端**直接读 Sir Chrome 加密 DB**拿 tzzb.10jqka.com.cn cookie，**完全跳过 DSH** |
| 1 | 一键续期 | "刷新验证"按钮调 refresh，**后端不重读源** | 按钮**改名"一键续期"**，强制后端从 L0→L1→L2 重新读 cookie |
| 2 | 自动续期 | token 失效只落 error，sir 必须手动操作 | 5min 后 cron 自动重读 Chrome DB（Chrome Cookie 自然续期就生效） |
| 3 | 兜底扫码 | Sir Chrome 也没登录时死锁 | 前端加"扫码登录"按钮 → window.open 拉起同花顺账本扫码页 → Sir 微信扫 1 次 |

---

## §二 架构约束

**后端**（1 依赖 + 1 新文件 + 2 改 + 0 新表 0 新 cron）
- 加 `browser-cookie3==0.20.1` 到 `backend/requirements.txt`（PyPI 主流，已支持 Windows DPAPI + AES-GCM 解密 Chrome 90+ 加密 Cookie DB）
- 新增 `backend/app/services/chrome_cookie.py`（≤60 行）：暴露 `load_tzzb_cookie_from_chrome()` + `is_chrome_cookie_available()` 两个纯函数
- 改 `backend/app/services/ths_pnl.py:load_cookie()` 末尾加 L2 fallback：现有 yaml 读取后调 `chrome_cookie.load_tzzb_cookie_from_chrome()`，非空则返（≤15 行净增）
- 改 `backend/app/api/routes.py:994` 后追加 `POST /api/account/pnl/login-link` 端点（≤20 行），仅在 ths_pnl_enable=true 时返 `scan_url` + `fallback_steps`
- **不重写** ths_pnl.py 的 fetch_pnl / fetch_index / get_snapshot / refresh_snapshot_if_needed 4 个核心函数
- **不动** DSH 凭证 yaml（**仅作 L1 fallback**，向后兼容）
- **不引新前端依赖**（仅用现有 antd Button + Space）

**前端**（1 文件 / ≤20 行净增）
- 改 `web/src/pages/OverviewPage.tsx:86-95` Cookie 过期卡片：
  - "刷新验证" 按钮 **改名**"一键续期"
  - 紧邻加"扫码登录"按钮，调 `POST /api/account/pnl/login-link` 拿 scan_url，window.open 拉起
  - 描述里加"Sir 已在 Chrome 登录？点「一键续期」自动从浏览器读取"
- **不引新依赖**（用现有 useTaskSubmit / message）

**自检脚本**（非必须，落 `D:\self\同花顺Cookie一键续期_自检脚本.bat` ≤15 行）
- `curl -s -X POST http://127.0.0.1:8000/api/account/pnl/refresh | jq`
- `curl -s -X POST http://127.0.0.1:8000/api/account/pnl/login-link | jq`
- 期望：refresh 返 `configured:true / token_expired:false`（chrome cookie 拿到后）；login-link 返 `chrome_cookie_available:true`

---

## §三 规则

| 项 | 规则 |
|---|---|
| 依赖 | `browser-cookie3==0.20.1`（pycookiecheat 0.6+ 改名版）—— 仅 backend，单 pip install |
| chrome_cookie 模块 | 零日志零打印（cookie 红色）；任何异常 `return ""`；`is_chrome_cookie_available()` 只检查包是否导入成功，不读 cookie 本体 |
| load_cookie L2 fallback | 优先级：L0(env) > L1(yaml) > **L2(Chrome DB)** > ""（L3 由前端触发） |
| 扫码登录端点 | 不返回任何 cookie；仅返 `scan_url` + `fallback_steps` + `chrome_cookie_available`；ths_pnl_enable=false 时返 503 |
| 前端按钮文案 | "刷新验证" → "一键续期"；扫码按钮仅在 L0~L2 全失败时显（默认显，给 Sir 兜底） |
| Chrome 锁 | browser-cookie3 读 Chrome Cookies SQLite 需 Chrome 已关；Sir Sir Chrome 在跑时 sqlite lock 失败 → `return ""` 落 L3 |
| 失败容错 | chrome_cookie 任何失败（包未装 / DB 锁 / 域无 cookie）一律 `return ""`，不阻塞 L0/L1 也不抛异常 |
| cookie 红色 | Chrome DB 读出的 cookie 走 `normalize_cookie()` 归一化（与 L0/L1 一致）；不写日志；不落库；不返前端 |

---

## §四 执行顺序

**前置：精准读文件**（不整读大文件）

```bash
grep -n "def load_cookie\|def normalize_cookie\|def _read_cred_block" backend/app/services/ths_pnl.py
grep -n "def account_pnl_refresh\|def account_pnl_login" backend/app/api/routes.py
grep -n "token_expired\|refresh验证\|DSH 插件" web/src/pages/OverviewPage.tsx
grep -n "ths_pnl_cookie\|browser-cookie" backend/requirements.txt
```

**步骤 1：加依赖 + 装包**
- `backend/requirements.txt` 末尾追加：`browser-cookie3==0.20.1`
- 本机 dev 装：`pip install browser-cookie3==0.20.1`（或项目 venv 路径）

**步骤 2：新建 chrome_cookie.py**（≤60 行）
- `backend/app/services/chrome_cookie.py` 新文件
- 实现 `load_tzzb_cookie_from_chrome()` + `is_chrome_cookie_available()`
- 沿用 ths_pnl.py 风格：模块 docstring ≤ 3 行；不写注释；except Exception → return ""

**步骤 3：改 ths_pnl.py load_cookie() 加 L2 fallback**（≤15 行）
- 在 `backend/app/services/ths_pnl.py:63-72` 函数末尾，return "" 前加 1 段
- 复用现有 `normalize_cookie()` 归一化

**步骤 4：新增 login-link 端点**（≤20 行）
- `backend/app/api/routes.py:994` 后追加 `@router.post("/account/pnl/login-link")` 函数
- 内部用 `is_chrome_cookie_available()` 给前端按钮显隐用
- 不返回任何 cookie

**步骤 5：前端改 OverviewPage.tsx**（≤20 行）
- `web/src/pages/OverviewPage.tsx:88-94` Alert description 里改按钮 + 加扫码按钮
- "刷新验证" 改名"一键续期"
- 新增"扫码登录"按钮：onClick 调 `post('/account/pnl/login-link', {})` → 拿 scan_url → window.open → message.info 引导
- 描述文案改"Sir 已在 Chrome 登录？点「一键续期」自动从浏览器读取"

**步骤 6：测试**（≤3 个新单测，沿用现有 mock 风格）
- `backend/tests/test_ths_pnl.py` 末尾追加：
  - `test_load_cookie_falls_back_to_chrome_db(monkeypatch)`：mock `chrome_cookie.load_tzzb_cookie_from_chrome` 返非空 → 断言 load_cookie 走 L2
  - `test_load_cookie_chrome_db_empty_returns_empty(monkeypatch)`：mock chrome 返空 → 断言返空
  - `test_load_cookie_priority_env_over_chrome(monkeypatch)`：env 非空时**不**调 chrome（monkeypatch 监测调用次数 = 0）
- **不写新测试 chrome_cookie.py 内部**（该模块读真 DB，单测意义小）

**步骤 7：执行 + 提交**
- `cd backend && python -m py_compile app/services/chrome_cookie.py app/services/ths_pnl.py app/api/routes.py`（语法）
- `cd backend && python -m pytest tests/test_ths_pnl.py -v`（3 新测试 + 既有 23 测试全 pass）
- `cd web && npm run build`（前端通过）
- 跑自检脚本
- **3 段分 3 commit**（后端 1 / 前端 1 / 文档 1）：
  - `feat(ths-pnl): chrome cookie DB L2 fallback + login-link 端点（cookie 一键续期）`
  - `feat(web): 同花顺 Cookie 过期卡片加"扫码登录"按钮 + 改"一键续期"文案`
  - `docs(ths-pnl): 落 同花顺Cookie一键续期_方案.md + 自检脚本`

---

## §五 验证清单

- [ ] `pip list | grep browser-cookie3` 显 0.20.1
- [ ] `curl -X POST /api/account/pnl/login-link` 返 `scan_url` + `chrome_cookie_available:true`
- [ ] Sir Chrome **已关闭**时，`curl -X POST /api/account/pnl/refresh` 返 `token_expired:false`（L2 命中）
- [ ] Sir Chrome **开启**时（同花顺账本未关），curl refresh 返 `token_expired:true`（L2 失败落 error，正常）
- [ ] 3 新单测 + 23 既有测试全 pass
- [ ] `py_compile` + `npm run build` 双通过
- [ ] git 3 commit 干净，工作区不混批
- [ ] 浏览器硬刷 Overview 页 → Cookie 过期卡片显"一键续期"+"扫码登录"双按钮
- [ ] 点"一键续期"：Sir Chrome 已关时 → 5s 内弹"今日盈亏"数字（不再"数据缺失"）
- [ ] 报告 ≤ 10 行：①改了什么（4 文件清单）②测试结果（26 passed）③遗留风险

**Codex 端省 token 6 条**（本批内置）
1. 6 段 + Schema + 阈值已在本文件齐备，禁止再次 read `D:\self\同花顺Cookie一键续期_方案.md` 全文
2. 只动 5 个文件：`backend/requirements.txt` / `backend/app/services/chrome_cookie.py`（新）/ `backend/app/services/ths_pnl.py` / `backend/app/api/routes.py` / `web/src/pages/OverviewPage.tsx`；禁止顺手改其他文件
3. 函数 docstring ≤ 3 行，函数体内不写 `# 注释`（除关键 trade-off）
4. 复用现有 `normalize_cookie()` / `_read_cred_block()` / `monkeypatch` 风格，禁止重写
5. 测试不写超过 3 个新单测（本批规定 3 个），禁止多写"以防万一"
6. 报告 ≤ 10 行：①改了什么（4 文件清单 + 1 依赖）②测试结果（pytest passed 数 + build 状态）③遗留风险

**代码侧最小改动铁律**：后端 ≤ 100 行（chrome_cookie.py 60 + ths_pnl.py 15 + routes.py 20 + requirements 1） / 前端 ≤ 25 行（OverviewPage.tsx 净增） / 测试 ≤ 50 行。超 → 停下报告 sir。

---

## §六 红线

1. **不动** ths_pnl.py 4 个核心函数（fetch_pnl / fetch_index / get_snapshot / refresh_snapshot_if_needed）—— 业务算法红线，sir 决策
2. **不动** DSH 凭证 yaml 逻辑（**仅作 L1 fallback**，向后兼容；Sir 仍可在 DSH 登录）
3. **不写日志 / 不打印**任何 cookie 值（ths_pnl 红线扩展到 chrome_cookie.py）
4. **不返回 cookie** 到 response body（login-link 仅返 scan_url）
5. **不引前端新依赖**（仅用现有 antd Button + Space + message）
6. **不改 cron 时间**（沿用 9:15 / mid / 16:00）
7. **不删** `useTaskSubmit` 调用（其他任务还在用，本批仅改 OverviewPage 一处按钮）
8. 改动行数超预算 → **停下报告 sir**，不要自行加功能
9. browser-cookie3 任何异常（包未装 / DB 锁 / 域无 cookie）**必须** `return ""` 不抛（与现有 ths_pnl 红线一致）

---

## §七 验收 SOP

1. `pip install browser-cookie3==0.20.1` + 重启后端
2. 浏览器硬刷 Overview 页（Ctrl+Shift+R）
3. Sir **关闭** Chrome → 点"一键续期" → 应 5s 内显"今日盈亏"
4. Sir **开启** Chrome → 点"扫码登录" → 新窗口扫码 → 登录后回首页 → 点"一键续期" → 应 5s 内显数字
5. `curl -X POST /api/account/pnl/refresh | jq` → `configured:true / token_expired:false`
6. `cd backend && python -m pytest tests/test_ths_pnl.py -v` → 26 passed
7. git status 干净，3 commit 落盘
