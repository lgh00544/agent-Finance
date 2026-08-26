# ReviewsPage 建议状态映射修复

## 目标

`D:\self\web\src\pages\ReviewsPage.tsx` 单文件改：补 SUG_STATUS 缺失的 `adopted` / `rejected` 两条映射，让 tag 颜色与中文文案一致。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| L28-31 SUG_STATUS 表 | 补 `adopted: { label: '已采纳', color: 'green' }` + `rejected: { label: '已驳回', color: 'default' }` | approved 与 adopted 同色（都是"已采纳"语义） |

## 修复前 vs 修复后

| status 值 | 修复前显示 | 修复后显示 |
|---|---|---|
| pending | 待审核（橙） | 待审核（橙） |
| approved | 已采纳（绿） | 已采纳（绿） |
| **adopted** | **adopted（默认灰）❌** | **已采纳（绿）✅** |
| **rejected** | **rejected（默认灰）❌** | **已驳回（灰）✅** |
| 其它 | 原样 | 原样 |

## 红线

1. 不动后端 / API / 类型
2. 不引入新依赖
3. 仅补 SUG_STATUS 两条映射，不动其它逻辑
4. approved 与 adopted 同色（都是"已采纳"），不区分
5. 不动详情抽屉（drawer 已经显示"已采纳并生效"/"已驳回"，行为正确）
6. 不动 AI 自动决策 banner / 三按钮
7. 提交时只改这一个文件

## 验收清单

- [ ] tsc --noEmit 0 error
- [ ] oxlint src/pages/ReviewsPage.tsx 0 error
- [ ] 列表「建议状态」列：pending=待审核(橙) / approved=已采纳(绿) / adopted=已采纳(绿) / rejected=已驳回(灰)
- [ ] 不再出现英文 "adopted" / "rejected" fallback
- [ ] 详情抽屉文案不变（已采纳并生效 / 已驳回）
