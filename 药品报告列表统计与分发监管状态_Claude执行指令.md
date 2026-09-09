# Claude Code 执行指令

请在当前项目中实现“药品报告列表统计与分发监管状态升级”。

详细业务口径参见《药品报告列表统计与分发监管状态_方案.md》§3-§7。不要仅根据截图猜测数据库字段；先以代码中的 `/api/pharma/report/list` 路由、查询服务、DTO 和前端消费者为准。

## 执行目标

1. 新增报告统计接口，统计跟随报告列表的公共筛选条件。
2. 统计顶部页签：全部、待办报告、自发报告、反馈报告、首次报告、跟踪报告、无效报告。
3. 待办报告必须按报告主键去重：一份报告只要任一语言/区域的审核状态为 `70200004` 或为空，就计为 1 份待办。
4. 将列表返回的 `reportAreaSign` 从旧格式：

   ```text
   70160001,70160002
   ```

   升级为：

   ```text
   70160001;70200004,70160002;70200001/70200002/70200003/70200005
   ```

5. 前端分发监管列按审核状态展示：`70200004` 或空值为处理中并返回 `10040002`；`70200001/70200002/70200003/70200005` 为已处理并返回 `10040001`。
6. 统计返回的每个数量都是可点击的列表筛选条件；点击后，列表实际总数必须等于对应统计值。

## 实施要求

1. 先使用 `rg` 定位：
   - `/api/pharma/report/list`；
   - `reportAreaSign` 的定义、赋值和所有消费者；
   - 顶部页签计数及其现有筛选参数；
   - 语言/区域审核状态的真实来源；
   - 相关测试和项目接口命名规范。
2. 复用列表已有的鉴权、租户、软删除、数据权限和公共筛选条件；不要复制一套会漂移的查询逻辑。
3. 新统计接口建议命名为 `GET /api/pharma/report/statistics`，如项目已有命名规范则按项目规范调整。
4. 给 `/api/pharma/report/list` 增加一个单值分类筛选参数，建议命名为 `reportCategory`；若项目已有命名规范则遵循现有规范。建议枚举值：

   ```text
   all | pending | selfReport | feedbackReport | initialReport | followUpReport | invalidReport
   ```

   不建议新增七个独立布尔参数。未传或传 `all` 查询全部，其余值分别查询对应页签。
5. 统计不受页码、每页数量、排序影响，不能只统计当前分页。
6. `total` 使用公共筛选条件；各分类字段在公共筛选条件上叠加自己的分类条件。各分类数量可以重叠，不要求相加等于总数。
7. 列表接口必须使用同一套公共条件和分类谓词：

   ```text
   list(reportCategory=all).total == statistics.total
   list(reportCategory=pending).total == statistics.pending
   list(reportCategory=selfReport).total == statistics.selfReport
   list(reportCategory=feedbackReport).total == statistics.feedbackReport
   list(reportCategory=initialReport).total == statistics.initialReport
   list(reportCategory=followUpReport).total == statistics.followUpReport
   list(reportCategory=invalidReport).total == statistics.invalidReport
   ```

   上述等式要求在公共筛选条件完全相同的情况下成立。`list.total` 是符合条件的报告总数，不是当前分页数组长度。若存在语言明细 join，列表结果和分页总数都必须按报告唯一主键去重。
8. 建议返回以下字段，若项目统一响应包装则放入既有 `data`：

   ```json
   {
     "total": 0,
     "pending": 0,
     "selfReport": 0,
     "feedbackReport": 0,
     "initialReport": 0,
     "followUpReport": 0,
     "invalidReport": 0
   }
   ```

9. `reportAreaSign` 必须按以下规则生成：
   - 逗号分隔语言/区域；
   - 分号分隔区域编码和状态串；
   - 斜杠分隔同一区域的多个状态；
   - 同一区域状态去重；
   - 顺序稳定；
   - 原始审核状态为 `70200004` 或空值时，前端显示处理中，结果编码为 `10040002`；
   - 原始审核状态为 `70200001`、`70200002`、`70200003` 或 `70200005` 时，前端显示已处理，结果编码为 `10040001`；
   - 必须按完整状态编码判断，不能使用模糊字符串包含。
10. 前端解析需兼容空值、旧格式和异常格式，不能因单条数据异常导致整列或整页崩溃。
11. 不新增无关重构，不修改截图未提出的布局和业务流程。

## 测试验收

新增或修改最小范围的直接相关测试，至少验证：

1. 公共筛选条件会作用于统计结果。
2. 分页参数不会影响统计结果。
3. 列表接口未传分类或传 `all` 时的 `list.total` 等于统计 `total`。
4. 点击每个分类页签后，列表的 `list.total` 等于对应统计字段。
5. 单语言状态为 `70200001/70200002/70200003/70200005` 时不计待办。
6. 多语言中一个 `70200004` 或空值计 1 份待办。
7. 多语言中存在多个 `70200004` 或空状态时仍只计 1 份待办。
8. 多份报告按报告数而非语言明细数计数。
9. `reportAreaSign` 新格式生成正确，状态去重且顺序稳定。
10. `70200004`/空值返回 `10040002`，其他四个已处理状态返回 `10040001`。
11. 空值、旧格式、异常格式不会导致前端报错。
12. 现有列表分页、搜索、重置和权限条件不回归。

执行结束后只汇报：

- 改动文件及关键行号；
- 测试 passed/failed 数量；
- 接口请求/响应示例；
- 尚未解决的问题或需要产品确认的口径。
