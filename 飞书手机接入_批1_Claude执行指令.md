# 飞书手机接入_批1_Claude执行指令.md

## 0 元信息
- 主题：飞书机器人桥 P0 文本通道（收文本 + 关键词路由 + 直发回复 + 告警直发）
- 方案：参见 `D:\self\飞书手机接入_方案.md` §3 / §5.1 / §5.2 / §5.6 / §6 / §8 R1 / §9
- 前置：sir 已在飞书开放平台建好自建应用（机器人能力 + `im:message` / `im:message:send_as_bot` / `im:resource` 权限 + 长连接事件 `im.message.receive_v1` + 已发布）；App ID/Secret 已填 .env

## 一 目标
手机飞书 1v1 与机器人对话：文本指令（查持仓 / 今日盈亏 / 帮助 / 系统状态）收到回复；Monitor 等告警可机器人直发手机；默认 `FEISHU_BOT_ENABLE=false` 零加载零依赖。

## 二 架构约束
1. 桥在 FastAPI 进程内运行：main.py lifespan 启动/停止（参照 `main.py:22-53`）
2. 用官方 SDK lark-oapi 长连接（`lark.ws.Client` + `P2ImMessageReceiveV1Handler`）；若 pip 装不上（**先 `D:\self\.venv\Scripts\python.exe --version` 自验，本机 venv 实测 Python 3.14.3；官方 Classifier 最高声明 3.12，兼容未知**）→ 停下报告 sir，**由 sir 拍板**（方案 R1 的 websockets 手写 fallback 仅作备选，不在本批默认动作内）
3. 白名单：事件入口校验 sender `open_id ∈ FEISHU_ADMIN_OPEN_IDS`，非白名单直接忽略；未配置白名单时打印首条消息 open_id 供 sir 填入（只打 open_id，不打内容）
4. 不新建业务逻辑：查询全部复用现有 service（`holding_view.py:64` / `:122`、`ths_pnl.py:179`、`status.py:86`）
5. 批1 仅关键词快路径（正则路由），LLM 智能路由批2 再上
6. 告警双通道：webhook 保留 + `FEISHU_BRIDGE_ALERT_DIRECT=true` 时直发；只改 `feishu.py:16-46 push_alert` 内部，调用方（`monitor.py:21` / `portfolio_sentinel.py:24` / `pre_market_screen.py:14`）零改动

## 三 规则
1. 新文件：
   - `backend/app/services/feishu_sender.py`：直发文本；**token 用 SDK `lark.Client` 获取，不手写 REST token 缓存**；POST `/open-apis/im/v1/messages?receive_id_type=open_id`，`msg_type=text`
   - `backend/app/services/feishu_bridge.py`：长连接 + 白名单 + 分发 + `_route_keyword()` 关键词路由；image/media/file 回「暂不支持（批3 上线）」；维护 `connected/last_event_at`
2. 配置：`config.py:73`（`feishu_webhook_url` 段后）追加 6 字段：`FEISHU_BOT_ENABLE` / `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_ADMIN_OPEN_IDS` / `FEISHU_BRIDGE_ALERT_DIRECT` / `FEISHU_MEDIA_DIR`；`.env.example` 同步加段（默认值/含义沿用方案 §5.6）
3. 回复文案：查持仓→摘要（持仓数/总市值/今日盈亏/持仓列表前 N 只）；今日盈亏→ths_pnl 三态（`configured:false` 回「未接入」/ `token_expired` 回「Cookie 过期请到 DSH 插件重新登录」/ 正常回 ¥与%）；未识别→回「未识别指令」+ 可用指令列表
4. 异常兜底：任何 handler 异常回「处理失败: {短错误}」不崩溃；桥线程异常只记日志，不拖垮主服务
5. 密钥：App Secret 只进 .env；日志不打 secret / cookie / 消息内容
6. 状态端点：routes.py 加 `GET /api/feishu/status` → `{bridge_enabled, connected, last_event_at, admin_count}`（`bridge_enabled`=配置开关、`connected`=实际连接态，二者区分便于运维；零业务逻辑）

## 四 执行顺序
1. `backend/requirements.txt` 加 `lark-oapi` → **先 `D:\self\.venv\Scripts\python.exe --version` 自验** → `pip install lark-oapi` 验证（兼容未知先装先验；失败停报 sir）
2. `config.py` 加字段 + `.env.example` 加段
3. 写 `feishu_sender.py`（SDK token + 发文本）
4. 写 `feishu_bridge.py`（ws.Client + on_message → 白名单 → `_route_keyword()`）
5. `feishu.py:16-46` 扩展直发通道（配置才生效，失败降级 webhook，不阻断）
6. `main.py:27` 后加 `start_feishu_bridge()`（`ENABLE=true` 才启动）、`:49` 区加 stop
7. routes.py 加状态端点 → 自测 + pytest 回归

## 五 验收
1. `FEISHU_BOT_ENABLE=false`：pytest 全绿、服务正常启动、无 lark-oapi 相关报错
2. true + 完整配置（**前提：`FEISHU_ADMIN_OPEN_IDS` 已填**；未填时按 §二.3 只打 open_id 不回复）：手机发「你好」→回复；「查持仓」→持仓摘要；「今日盈亏」→三态正确；「帮助」→指令列表
3. 非白名单账号发消息 → 无响应
4. mock 一条 Monitor 高危告警 → webhook + 直发都收到；直发失败降级不抛
5. grep 校验日志无 App Secret / Cookie 泄露

## 六 红线
1. 只做查询/任务触发，不新增任何交易/下单代码
2. 默认关零加载；全部改动 ≤250 行（2 新文件 + 3 改动文件）
3. 密钥仅 .env，严禁硬编码/进日志/进 git
4. 不修改 agent 研判逻辑/策略/阈值
5. **Claude Code 端省 token**：不重复读提示词已固化信息；不写超范围代码（提示词列了哪几个文件就只动那几个）；docstring ≤3 行；函数体内不写 `# 注释`（除关键 trade-off）；复用现有函数禁止重写；测试只写规定数量；报告 ≤10 行（改了什么 / 测试结果 / 遗留风险）。代码改动预算 ≤80 行，超出停下报告 sir。
