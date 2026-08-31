# 飞书手机接入_批3_Claude执行指令.md

## 0 元信息
- 主题：P2 多媒体（图片识别 + 视频/文件收存）
- 方案：参见 `D:\self\飞书手机接入_方案.md` §5.4 / §6 / §8 R6
- 前置：批2 已验收

## 一 目标
手机发图片（持仓截图/任意图）→ 识别回传，持仓图人工确认后落库；视频/文件收存并告知；临时文件即用即删。

## 二 架构约束
1. 图片下载：`GET /open-apis/im/v1/messages/{message_id}/resources/{file_key}?type=image` → 临时文件（tempfile）
2. 持仓截图识别：**主路径用 minimax 多模态**（`multimodal.py:151` `get_multimodal_client` → `multimodal.py:53` `analyze_image`，提示词显式要求返回结构化持仓字段）；`MINIMAX_ENABLE=false` 或调用失败 → fallback `ocr.py` 本地 PaddleOCR；再失败 → 回「图片已收到，无法识别内容」。`OCR_ENABLE=false` 时跳过 paddle 兜底；识别结果回发预览 → 用户回「确认」才落库、「取消」丢弃；pending 5 分钟过期（bridge 内存表）
3. 落库：复用现有入库链路（参照 routes.py `POST /holdings` 与 `POST /ocr/holding` 背后实现，grep 定位）
4. 非持仓图：直接走 `analyze_image`（minimax 开启时）描述图片内容；未启用 minimax → 回「图片已收到，无法识别内容」（不调 paddle 兜底，避免无意义开销）
5. 视频/文件：下载到 `settings.feishu_media_dir`（默认 `data/feishu_media/`）→ 回「已收到并保存」；**不解析、不引入 ffmpeg**
6. 清理：临时文件 finally 删除；media_dir 启动时清理 >7 天文件

## 三 规则
1. 类型与大小校验：image 限 png/jpg/jpeg/webp/bmp ≤10MB；video/file/media ≤50MB；超限统一回「文件过大：图片限 10MB、视频限 50MB」
2. 识别优先级：minimax 云端主路径（`MINIMAX_ENABLE=true`）→ PaddleOCR 本地兜底（`OCR_ENABLE=true` 且 minimax 失败/关闭）→ 回「图片已收到，无法识别内容」（双通道都不可用）
3. 幂等：同一 file_key 5 分钟内不重复处理（内存缓存）
4. 确认交互：pending 表字段 `{open_id, file_key, ocr_result, expires}`；「确认/取消」关键词在路由中优先于其他意图
5. **识别结果绝不自动落库，必须人工确认**（延续「人工控制入口」哲学，与网页端录入同规则）
6. 图片仅临时文件处理，不长期留存用户截图（延续 ocr.py 原则）；全部改动 ≤250 行

## 四 执行顺序
1. bridge 补 image/media/file 分发（批1 已留位）
2. image handler：下载 → 临时文件 → minimax 主识别（持仓 prompt / 通用 prompt 按图片意图分支）→ 失败/未启用 fallback paddle → 预览回发 → pending 登记
3. 确认/取消处理 → 落库/丢弃（复用现有 repo 入库，grep 定位）
4. 非持仓图：直接 minimax 描述（未启用 → 回「图片已收到，无法识别内容」，不调 paddle 兜底）
5. video/file 下载存档 + media_dir 启动清理
6. 自测（mock 下载 + minimax 关闭路径 + paddle 关闭路径）+ pytest 回归

## 五 验收
1. 手机发持仓截图 → 收到结构化预览 → 回「确认」→ 落库后「查持仓」能查到
2. 发普通图片（MINIMAX 开）→ 收到内容描述
3. 发视频 → 收到「已保存」且文件在 media_dir
4. `MINIMAX_ENABLE=false` 且 `OCR_ENABLE=false` → 明确回「图片已收到，无法识别内容」，不报错；仅 paddle 可用 / 仅 minimax 可用场景由 §三.2 优先级自动兜底
5. 临时文件无残留；pytest 全绿

## 六 红线
1. 人工确认才落库；识别结果仅供预览
2. 视频不解析、不引 ffmpeg 依赖
3. 图片即用即删，不留存
4. 不新增交易能力；不修改研判逻辑
5. Claude Code 端约束：不重复读提示词已固化信息；不写超范围代码；docstring ≤3 行；复用现有函数禁止重写；测试只写规定数量；报告 ≤10 行
