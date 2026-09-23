# 同花顺 Cookie 一键续期方案（DSH 解耦 + 4 级 fallback + 扫码兜底）

> 生成日期：2026-09-15
> 触发：sir 反馈"我已经登录同花顺网页版并点了刷新，sir 想跳过 DSH 一次性解决 + 后续 0 操作"
> 现状：ths_pnl.py 走 DSH 凭证 yaml（同花顺账本 cookie httpOnly，DSH 单独开 Electron 窗口登录拿）
> 目标：sir 只要 Chrome 已登录同花顺账本，**后续永远 0 操作**；失效兜底扫码 1 次

## 一、现状 & 痛点

| 段 | 现状 | 痛点 |
|---|---|---|
| cookie 源 | DSH 凭证 yaml | DSH 自己开 Electron 窗口登录，**sir 自己的 Chrome 登录态没用** |
| 后端 cron | 9:15 / mid / 16:00 跑 `ths_pnl_job`（jobs.py:1027-1039） | token 失效只落 `error="TOKEN_EXPIRED"`，不自动续 |
| 前端 | `OverviewPage.tsx:88` 提示"请在 DSH 插件中完成自动获取并保存" | **必须切 DSH**；sir 自己的 Chrome 没用上 |
| token 失效 | 同花顺账本 cookie `httpOnly` | devtools 看不到，JS 读不到；sir 在自己 Chrome 登录了**没用** |

## 二、目标

**一劳永逸**：
1. **主路径零操作**：sir Chrome 已登录同花顺账本 → 后端直接从 Chrome Cookies DB 解密拿 cookie → cron 自动续期 → sir 永远不用打开 DSH
2. **兜底扫码 1 次**：Chrome Cookie DB 失败时，前端弹扫码登录按钮 → sir 微信扫 1 次 → 写回 yaml + 同步给 Chrome → 后续 cron 永远拿到
3. **完全解耦 DSH**：ths_pnl.py 不再依赖 DSH 凭证文件作为唯一源

## 三、4 级 fallback（按优先级）

| 优先级 | 源 | 实现位置 | 何时用 |
|---|---|---|---|
| L0 | `env THS_PNL_COOKIE` | `ths_pnl.py:load_cookie()` 已支持 | 永远先试 |
| L1 | DSH yaml（现状） | `ths_pnl.py:load_cookie()` 已支持 | L0 空 |
| L2 | **Sir Chrome Cookies DB**（**新增**） | `chrome_cookie.py` 新文件 + `load_cookie()` 加 1 段 fallback | L1 失败/失效 |
| L3 | **前端扫码登录**（**新增**） | 新 endpoint `POST /api/account/pnl/login-link` + `OverviewPage.tsx` 加按钮 | L2 失败（**几乎不会到 L3**） |

## 四、后端改动（4 文件 / 1 依赖 / 0 新表）

### 4.1 新依赖：pycookiecheat 0.6+
- 读 Chrome / Chromium / Edge 加密 cookie 库（DPAPI + AES-GCM 已支持）
- 加到 `backend/requirements.txt`
- 范围：仅 backend，**前端零改动**

### 4.2 新文件：`backend/app/services/chrome_cookie.py`（≤60 行）

```python
# -*- coding: utf-8 -*-
"""从 Sir 本机 Chrome 加密数据库解出 tzzb.10jqka.com.cn 域 cookie
仅 ths_pnl 内部调用，零对外暴露；不写日志/不打印/不落库。
"""
import logging
from typing import Optional
logger = logging.getLogger(__name__)

DOMAIN = "tzzb.10jqka.com.cn"

def load_tzzb_cookie_from_chrome() -> str:
    """读 Sir Chrome 的 tzzb.10jqka.com.cn cookie 字符串；任何失败返空串"""
    try:
        import browser_cookie3  # type: ignore
    except ImportError:
        return ""
    try:
        cj = browser_cookie3.chrome(domain_name=DOMAIN)
    except Exception:
        return ""
    items = [f"{c.name}={c.value}" for c in cj if c.domain.endswith("10jqka.com.cn")]
    return "; ".join(items)

def is_chrome_cookie_available() -> bool:
    """前端按钮显隐判断：环境就绪即 True（不读 cookie 本体）"""
    try:
        import browser_cookie3  # noqa: F401
        return True
    except ImportError:
        return False
```

**设计要点**：
- `browser_cookie3` 是 `pycookiecheat` 0.6+ 用的导入名（pycookiecheat 0.6 改包名为 browser_cookie3）  
- `domain_name` 参数只取该域 cookie，**不读其他域**（最小权限）  
- 失败一律 `return ""`（沿用 ths_pnl 红线：失败只落 error，不抛）  
- 不写日志/不打印（cookie 红色）  
- Chrome 必须已关才能读 sqlite 锁——前端按钮显隐判断走 `is_chrome_cookie_available()` 告诉 sir "先关 Chrome 再点扫码"

### 4.3 改 `backend/app/services/ths_pnl.py:load_cookie()`（≤15 行净增）

```python
# ths_pnl.py:load_cookie() 末尾，return 前加 L2 fallback
from app.services.chrome_cookie import load_tzzb_cookie_from_chrome
chrome_cookie = load_tzzb_cookie_from_chrome()
if chrome_cookie:
    return normalize_cookie(chrome_cookie)
return ""  # L0/L1/L2 全空，L3 走前端扫码
```

**改动行数**：净增 ≤15 行；现有 3 个测试不破坏（mock `chrome_cookie` 函数即可）

### 4.4 新端点：`POST /api/account/pnl/login-link`（≤20 行）

```python
# backend/app/api/routes.py:994 后追加
@router.post("/account/pnl/login-link")
def account_pnl_login_link():
    """L2/L1/L0 全失败时返扫码登录 URL；sir 微信扫 1 次拿到 cookie 写回 yaml"""
    if not settings.ths_pnl_enable:
        return {"configured": False, "error": "ths_pnl 未启用"}
    from app.services import ths_pnl as svc
    from app.services.chrome_cookie import is_chrome_cookie_available
    return {
        "configured": False,
        "scan_url": "https://tzzb.10jqka.com.cn/pc/index.html",
        "fallback_steps": [
            "1. 在 Sir Chrome 中打开上方链接，微信扫码登录同花顺账本",
            "2. 登录后保持 Chrome 打开（不要关）",
            f"3. {('浏览器冲突时 ' + '请先关闭 Chrome 后再点刷新') if is_chrome_cookie_available() else 'sir Chrome 未装 L2 自动续期'}"
        ],
        "chrome_cookie_available": is_chrome_cookie_available(),
    }
```

**设计要点**：
- 不返回 cookie（**红线：禁止 cookie 出现在 response body**）  
- 返 `scan_url` + `fallback_steps` 引导 sir 走 L3  
- 前端按钮仅在 L0/L1/L2 全失败时显

## 五、前端改动（1 文件 / ≤20 行）

### 5.1 改 `web/src/pages/OverviewPage.tsx:86-95`（Cookie 过期卡片）

```tsx
// 第 88-94 行卡片里加 "扫码登录" 按钮（L0~L2 全失败时显）
{expired ? (
  <Alert type="warning" showIcon style={{ marginTop: 2, padding: '4px 8px' }}
    message="🍪 同花顺 Cookie 已过期"
    description={
      <>
        <a href="https://tzzb.10jqka.com.cn/pc/index.html" target="_blank" rel="noreferrer">同花顺账本 · 重新登录</a>
        <div style={{ fontSize: 12, opacity: 0.75, marginTop: 4 }}>Sir 已在 Chrome 登录？点「一键续期」自动从浏览器读取</div>
        <Space size="small" style={{ marginTop: 6 }}>
          {onRefresh ? <Button size="small" loading={refreshing} onClick={onRefresh}>一键续期</Button> : null}
          <Button size="small" onClick={async () => {
            const r = await post('/account/pnl/login-link', {})
            if (r?.scan_url) window.open(r.scan_url, '_blank', 'noopener')
            message.info('请在新窗口扫码登录，登录后回到本页点「一键续期」')
          }}>扫码登录</Button>
        </Space>
      </>
    } />
) : null}
```

**设计要点**：
- 按钮文案从"刷新验证"改为"一键续期"（语义清晰）  
- 加"扫码登录"按钮作为 L3 兜底  
- 微信扫码由前端 `window.open` 拉起，不走后端

## 六、验收

1. **Sir Chrome 已登录同花顺账本**（截图证明）
2. 跑后端 `pip install browser-cookie3` + 重启
3. 浏览器硬刷 Overview 页 → 点"一键续期" → 应 5s 内从 Chrome DB 读出 cookie
4. 5min 后 cron 自动采集 → 今日盈亏正常显（不再"数据缺失"）
5. **验收后 7~30 天**：sir 在 Chrome 里**自动**续期登录（sir 自己日常用 Chrome）→ cookie 自动刷新 → 整个链路对 sir 透明

## 七、批次（单批次 1 指令 ≤150 行）

| 段 | 内容 | 行数预算 |
|---|---|---|
| §0 | 元信息 + 关联文件 | 15 |
| §一 | 目标 + 4 级 fallback | 25 |
| §二 | 后端 4 文件改动 | 30 |
| §三 | 前端 1 文件改动 | 15 |
| §四 | 执行顺序（8 步） | 30 |
| §五 | 验证清单 | 10 |
| §六 | 红线（8 条） | 25 |
| §七 | 验收 SOP | 10 |

## 八、不动的事

1. 不重写 ths_pnl.py 4 个核心函数（fetch_pnl / fetch_index / get_snapshot / refresh_snapshot_if_needed）
2. 不动 DSH 凭证 yaml（**仅作 L1 fallback**）
3. 不改 cron 时间（沿用 9:15 / mid / 16:00）
4. 不动前端 OverviewPage 已有布局（仅 Alert 卡片里加按钮）
5. 不引新前端依赖（仅用现有 antd Button/Space）

## 九、关联引用

- 现状：ths_pnl.py:63 load_cookie / ths_pnl.py:222 refresh_snapshot_if_needed
- 前端：OverviewPage.tsx:86-95 Cookie 过期卡片
- cron：jobs.py:1027-1039 ths_pnl 三时段
- 测试：tests/test_ths_pnl.py 已有 23+ 个用例（mock 全部，需继续 mock-friendly）

