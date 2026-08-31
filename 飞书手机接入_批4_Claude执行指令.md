# 飞书手机接入_批4_Claude执行指令.md

## 0 元信息
- 主题：P3 增强（可选：卡片按钮交互 + 群聊 @ + 每日日报推送）
- 方案：参见 `D:\self\飞书手机接入_方案.md` §7 批4 / §8 R4
- 前置：批1-3 已验收；本批为增量增强，非必须，sir 确认后再执行。飞书后台所需额外权限/事件（`im:chat` / `im:chat.member` / `card.action.trigger`）已在方案 §4 步骤 3/4 补充，执行前先核对已开通

## 一 目标
交互升级：富文本卡片+按钮（确认/取消、翻页）、群聊 @ 机器人才响应、每日定时日报直发手机。

## 二 架构约束
1. 卡片：发送 `msg_type=interactive`（沿用 `feishu.py:31-38` 卡片样式扩展按钮）；按钮回调走事件 `card.action.trigger`（长连接同样支持，需飞书开放平台额外添加该事件）；回调 open_id 校验复用白名单
2. 群聊：需飞书开放平台额外开通 `im:chat` / `im:chat.member` 权限；事件 `chat_type=group` 时仅处理 @ 机器人的消息（text 中含机器人 open_id），单聊逻辑不变
3. 日报：scheduler 新增 job（参照 `scheduler/jobs.py` 现有 job 注册方式），每日收盘后直发：今日盈亏 + 持仓概览 + 当日候选/发现摘要 + 最新告警数；`FEISHU_DAILY_REPORT=true` 才启用
4. 状态端点：批1 已有 `GET /api/feishu/status`，本批仅扩展字段（如 `pending_count`），不新建端点

## 三 规则
1. 卡片「确认/取消」替代批3 的文本确认（pending 表兼容两种触发）
2. 群聊非 @ 消息一律忽略；群聊只回复 @ 自己的消息
3. 日报内容全部来自现有服务（`ths_pnl.py:179 get_snapshot` / `holding_view.py:64` / 最新候选 / alert 计数），禁止新写任何研判
4. 新增配置（默认关）：`FEISHU_DAILY_REPORT=false` / `FEISHU_DAILY_REPORT_HOUR=16` / `FEISHU_DAILY_REPORT_MINUTE=30`；`.env.example` 同步
5. 全部改动 ≤250 行；卡片 JSON 结构以飞书官方文档为准（按钮 `tag=button` + `value` 回传）

## 四 执行顺序
1. feishu_sender.py 扩展卡片发送（带按钮）
2. bridge 注册 `card.action.trigger` 事件处理 → 白名单 → 确认/取消/翻页动作
3. 群聊 @ 过滤（仅 text 类型处理 @）
4. scheduler 日报 job（关闭时零注册）
5. 状态端点补字段
6. 自测（mock 卡片事件 + 日报内容组装）+ pytest 回归

## 五 验收
1. 卡片按钮点击 → 对应动作生效（确认落库 / 取消丢弃）
2. 群里 @ 机器人 → 回复；不 @ → 不响应
3. `FEISHU_DAILY_REPORT=true` → 指定时间收到日报；false → 无
4. pytest 全绿；批1-3 已验收行为零回归

## 六 红线
1. 不新增交易/下单能力；不新增任何研判逻辑（日报只搬运现有服务结果）
2. 默认关，配置才启用
3. 密钥仅 .env；群聊内容不落日志
4. 不修改 agent 策略/阈值；不写超范围代码
5. Claude Code 端约束：不重复读提示词已固化信息；docstring ≤3 行；复用现有函数禁止重写；测试只写规定数量；报告 ≤10 行
